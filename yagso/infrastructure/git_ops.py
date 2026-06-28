"""Infrastructure layer for Git operations using gitpython."""
import os
import re
import stat
import git
import shutil
from pathlib import Path
from collections import OrderedDict
from typing import Dict, List, Any, Optional
from git import Repo, Submodule, Git
from git.config import GitConfigParser
from contextlib import suppress
from ..domain.submodule import SubmoduleDefinition


def _remove_readonly(func, path, exc_info):
    """Reset read-only bits and retry filesystem removals."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


# Workaround: During Python interpreter shutdown on Windows, GitPython's
# AutoInterrupt destructor can invoke logging internals that may already be
# torn down, causing ``Exception ignored in: ...`` messages.  To avoid that
# noisy traceback we monkeypatch a safe __del__ wrapper that swallows any
# exception raised during finalization. This is a runtime-only workaround
# that keeps third-party site-packages untouched on disk.
try:
    import git.cmd as _git_cmd

    def _safe_autointerrupt_del(self):
        try:
            # Attempt to terminate the process as before, but swallow all
            # exceptions to avoid interpreter-shutdown races raising here.
            self._terminate()
        except Exception:
            pass

    if hasattr(_git_cmd, "_AutoInterrupt"):
        _git_cmd._AutoInterrupt.__del__ = _safe_autointerrupt_del
except Exception:
    # If anything goes wrong importing or monkeypatching, don't fail import.
    pass


class GitOperations:
    """Interface to Git commands using gitpython."""

    def is_same_repo(url1: str, url2: str) -> bool:
        """Check whether two repository URLs reference the same remote.

        This performs a lightweight check by asking each remote for the
        `HEAD` reference (using `git ls-remote HEAD`) and comparing the
        returned object names. This is useful to detect equivalent
        repositories where the URL form differs (for example HTTPS vs SSH).

        Args:
            url1: First repository URL.
            url2: Second repository URL.

        Returns:
            True if both URLs resolve to the same HEAD object name, False
            on mismatch or when the remote check fails.
        """
        g = Git()
        try:
            head1 = g.ls_remote(url1, 'HEAD').split()[0]
            head2 = g.ls_remote(url2, 'HEAD').split()[0]
            return head1 == head2
        except BaseException:
            return False

    # Helper to compare short/long SHA forms
    def sha_equal(a: Optional[str], b: Optional[str]) -> bool:
        """Return True when two commit-ish strings refer to the same commit.

        Accepts full or abbreviated commit SHAs (or tags/refs that have been
        resolved to SHAs). Returns ``False`` if either value is ``None`` or
        empty. The comparison treats one value being a prefix of the other as
        equality to support short vs long SHA forms.

        Args:
            a: first commit-ish string or ``None``.
            b: second commit-ish string or ``None``.

        Returns:
            ``True`` when the two strings are equal or one is a prefix of the other,
            otherwise ``False``.
        """

        if not a or not b:
            return False

        a = a.strip()
        b = b.strip()
        return a == b or a.startswith(b) or b.startswith(a)

    def __init__(self, repo_path: Path):
        """Initialize with repository path."""
        self.repo_path = repo_path
        self._repo: Optional[Repo] = None

    @property
    def repo(self) -> Repo:
        """Lazily construct and return a GitPython ``Repo`` for `self.repo_path`.

        Returns:
            A ``git.Repo`` instance rooted at `self.repo_path`.

        Raises:
            ValueError: if `self.repo_path` is not a valid Git repository.
        """

        if self._repo is None:
            try:
                self._repo = Repo(self.repo_path)
            except git.InvalidGitRepositoryError as e:
                raise ValueError(f"Not a valid Git repository: {self.repo_path}") from e

        return self._repo

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        # Ensure repository is closed when exiting context manager.
        # Use the shared `close()` helper for idempotent, safe shutdown.
        try:
            self.close()
        except Exception:
            # Swallow exceptions in __exit__ to avoid masking original errors.
            pass

    def close(self) -> None:
        """Close the GitPython Repo if opened.

        This is idempotent and swallows all exceptions because it may be
        invoked during interpreter shutdown where module-level state can be
        partially turn down.
        """
        repo = getattr(self, '_repo', None)
        if repo is None:
            return
        try:
            repo.close()
        except Exception:
            # Avoid raising from destructor/cleanup paths.
            pass
        finally:
            # Clear reference to allow GC and avoid double-close.
            try:
                self._repo = None
            except Exception:
                pass

    def __del__(self):
        # Do a minimal, defensive close here. Avoid calling other methods
        # that may depend on module-level globals during interpreter shutdown.
        repo = getattr(self, '_repo', None)
        if repo is not None:
            try:
                repo.close()
            except Exception:
                pass
            try:
                self._repo = None
            except Exception:
                pass

    def get_recorded_commit(self, path: str) -> Optional[str]:
        """Return the gitlink commit SHA for `path` recorded in `HEAD`.

        This reads the index/tree for `HEAD` and extracts the commit-like
        object id for the gitlink entry. If the path is not present or the
        Git command fails this returns ``None``.

        Args:
            path: relative path to the submodule/gitlink inside the repo.

        Returns:
            Commit SHA string (7-40 hex chars) if present, otherwise ``None``.
        """
        try:
            out = self.repo.git.ls_tree('HEAD', '--', path)
        except git.GitCommandError:
            return None

        out = (out or '').strip()
        if not out:
            return None

        # Expect a line like: "160000 commit <sha>\t<path>"
        m = re.search(r"commit\s+([0-9a-fA-F]{7,40})", out)
        if m:
            return m.group(1)
        return None

    def get_refs_containing_commit_at_path(self, worktree_path: Path, commit: str) -> List[str]:
        """Return refs in a worktree that point at the given `commit`.

        This inspects the repository at `worktree_path` and lists refs that
        directly point at the supplied `commit` (branches, tags and remotes).
        Symbolic HEAD refs are filtered out.

        Args:
            worktree_path: filesystem path to the repository to inspect.
            commit: commit-ish (SHA or ref) to check for.

        Returns:
            List of ref names (short form). Returns an empty list if the path
            is not a repository or the git command fails.
        """
        try:
            sub_repo = Repo(worktree_path)
        except git.InvalidGitRepositoryError:
            return []

        try:
            # Only list refs that point at the exact commit (no "contains").
            out = sub_repo.git.for_each_ref('--format=%(refname:short)', '--points-at', commit,
                                            'refs/heads', 'refs/tags', 'refs/remotes')
        except git.GitCommandError:
            return []

        if not out:
            return []

        # Build list and exclude any HEAD refs (local or remote symbolic refs)
        refs = [r.strip() for r in out.splitlines() if r.strip()]
        filtered = [r for r in refs if not re.search(r'(^HEAD$|/HEAD$)', r)]
        return filtered

    def get_submodules(self) -> List[Dict[str, Any]]:
        """Return a list of dictionaries describing configured submodules.

        Each returned dict contains the keys: ``name``, ``path``, ``url``,
        ``branch`` (may be ``None``), and ``commit`` (may be ``None`` when
        unavailable). This reads submodule metadata via GitPython which in
        turn reads `.gitmodules`.

        Returns:
            A list of simple dicts representing submodules.
        """
        submodules = []
        for submodule in self.repo.submodules:
            try:
                # This reads from .gitmodules
                reader = submodule.config_reader()
                tracking_branch = reader.get_value('branch')
            except Exception:
                # No 'branch' key in .gitmodules
                tracking_branch = None

            submodules.append({
                "name": submodule.name,
                "path": submodule.path,
                "url": submodule.url,
                "branch": tracking_branch,
                "commit": submodule.hexsha if submodule.hexsha else None,
            })
        return submodules

    def read_gitmodules_blocks(self) -> list:
        """Read configured submodules and return simple block dictionaries.

        This is a convenience wrapper around `get_submodules()` that converts
        the GitPython representation into the lightweight block format used
        elsewhere in the codebase: keys include ``name``, ``path``, ``url``
        and ``commit`` and optionally ``branch``.

        Returns:
            List of dicts representing `.gitmodules` entries.

        Raises:
            IOError: when reading via GitPython fails.
        """
        blocks = []
        try:
            for item in self.get_submodules():
                block = {
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "url": item.get("url"),
                    "commit": item.get("commit"),
                }
                if item.get("branch"):
                    block["branch"] = item.get("branch")
                blocks.append(block)
        except Exception as e:
            raise IOError(f"Failed to read submodules via GitPython: {e}") from e

        return blocks

    def is_git_repository(self) -> bool:
        """Return True when `self.repo_path` is a Git repository.

        Returns:
            True if `self.repo_path` can be opened by GitPython, False
            otherwise.
        """

        try:
            Repo(self.repo_path)
            return True
        except git.InvalidGitRepositoryError:
            return False

    def sync_submodule(self, submodule_def: SubmoduleDefinition, name: str) -> None:
        """Synchronize a single submodule to the given definition.

        This inspects the repository's `.gitmodules` (via GitPython's
        `config_reader`) and the on-disk submodule, then performs any of the
        following as needed to make the local submodule match
        `submodule_def`:
        - update submodule name (by removing and re-adding the submodule with the new name)
        - update the URL in `.gitmodules` and run `git submodule sync`
        - update the tracking branch (via `git submodule set-branch` or
          unset it)
        - checkout the requested commit/branch/tag/hash inside the submodule

        Args:
            submodule_def: SubmoduleDefinition describing desired state.
            name: the name of the submodule to sync (used for git commands).

        Raises:
            ValueError: if the submodule path does not exist in the filesystem.
            RuntimeError: if a git operation fails while applying changes.
        """

        try:
            submodule = self.repo.submodule(name)

            # Update name if it differs
            current_name = submodule.name
            if current_name != submodule_def.name:
                # Save submodule properties
                url = submodule.url
                path = submodule.path
                commit_sha = submodule.hexsha

                # Remove old submodule (keeps .git/modules)
                submodule.remove(force=False, module=True)

                # create new submodule with updated name and previous properties.
                # set wanted tracking branch (if any)
                submodule = self.repo.create_submodule(name=submodule_def.name, path=path, url=url,
                                                       branch=submodule_def.tracking_branch)

                # rewrite in git order (path, url, branch) to avoid unnecessary diffs
                # Determine the .gitmodules file path for this repository
                gitmodules_path = str(self.repo_path / '.gitmodules')
                config = OrderedGitConfigParser(gitmodules_path)
                config.read()
                with config:
                    pass

                # Checkout same commit
                submodule.module().git.checkout(commit_sha)

            # Update URL if it differs (handle https <-> ssh changes)
            current_url = submodule.url
            if current_url != submodule_def.url:
                self.repo.git.config('--file', '.gitmodules',
                                     f"submodule.{submodule_def.name}.url", submodule_def.url)
                self.repo.git.submodule('sync', '--', submodule_def.name)

            # Update tracking branch if it differs
            try:
                reader = submodule.config_reader()
                current_branch = reader.get_value('branch')
            except Exception:
                current_branch = None

            if current_branch != submodule_def.tracking_branch:
                if submodule_def.tracking_branch:
                    self.repo.git.submodule(
                        "set-branch",
                        "--branch",
                        submodule_def.tracking_branch,
                        submodule_def.name)
                else:
                    # Unset branch if tracking_branch is None or empty
                    self.repo.git.submodule("set-branch", "--unset", submodule_def.name)

            # Checkout the requested commit expressed by a branch/tag/hash in the submodule
            # Resolve commit-ish (branch/tag/hash) to a local SHA when possible and
            # compare it to the recorded gitlink before performing the checkout.
            sub_repo_path = self.repo_path / submodule_def.path
            if not sub_repo_path.exists():
                raise ValueError(f"Submodule path does not exist: {sub_repo_path}")

            current_commit = self.get_recorded_commit(submodule_def.path)
            desired_ref = submodule_def.commit

            # Only attempt resolution/checkout when a desired ref is provided
            if desired_ref:
                sub_repo = Repo(sub_repo_path)
                resolved_sha = None
                resolved_from_origin = False

                try:
                    resolved_sha = sub_repo.git.rev_parse(desired_ref)
                except Exception:
                    # Try on origin if local resolution fails
                    origin_ref = f'origin/{desired_ref}'
                    try:
                        resolved_sha = sub_repo.git.rev_parse(origin_ref)
                        resolved_from_origin = True
                    except Exception as e:
                        raise RuntimeError(
                            f"Failed to resolve sha of {desired_ref} in submodule {
                                submodule_def.name}") from e

                # TODO - Maybe checkout also if commit field is a branch even if equal
                if not GitOperations.sha_equal(current_commit, resolved_sha):
                    try:
                        if resolved_from_origin:
                            # Create a new local branch tracking origin
                            sub_repo.git.checkout(
                                "-b", desired_ref, "--track", origin_ref)
                        else:
                            sub_repo.git.checkout(desired_ref)
                    except Exception as e:
                        raise RuntimeError(
                            f"Failed to checkout {desired_ref} in submodule {
                                submodule_def.name}: {e}") from e

        except ValueError as e:
            raise ValueError(f"Submodule not found: {submodule_def.path}: {e}") from e
        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to sync submodule {submodule_def.name}: {e}") from e
        except git.exc.InvalidGitRepositoryError as e:
            raise RuntimeError(f"Submodule repository error for {submodule_def.path}: {e}") from e

    def add_submodule(self, submodule_def: SubmoduleDefinition) -> None:
        """Add a new submodule according to the SubmoduleDefinition.

        This method performs the high-level steps required to add a submodule
        to the repository:
        - Invoke `git submodule add` (optionally with a tracking branch).
        - Initialize and update the submodule working tree.
        - Attempt to checkout a requested commit or branch inside the
          newly-added submodule.
        - Stage the updated `.gitmodules` file and the submodule gitlink
          (the path) in the index.

        Args:
            submodule_def: A `SubmoduleDefinition` describing the submodule to add.

        Raises:
            RuntimeError: If any git operation fails (adding the submodule,
                checking out the requested ref, or staging the submodule path).
            ValueError: If the submodule repository is not present at the
                expected path after a successful `git submodule add`.
        """
        name = submodule_def.name
        path = submodule_def.path
        url = submodule_def.url
        desired_branch = submodule_def.tracking_branch
        desired_commit = submodule_def.commit

        # create new submodule
        submodule = self.repo.create_submodule(name=submodule_def.name, path=path, url=url,
                                               branch=submodule_def.tracking_branch)

        # rewrite in git order (path, url, branch) to avoid unnecessary diffs
        # Determine the .gitmodules file path for this repository
        gitmodules_path = str(self.repo_path / '.gitmodules')
        config = OrderedGitConfigParser(gitmodules_path)
        config.read()
        with config:
            pass

        # Initialize and update working copy
        submodule.update(recursive=True, init=True)

        # Checkout desired commit/branch
        if desired_commit:
            submodule.module().git.checkout(desired_commit)
        elif desired_branch:
            submodule.module().git.checkout(desired_branch)
        else:
            # No desired commit or branch specified, just checkout the default
            submodule.module().git.checkout()

        # Stage .gitmodules and the gitlink
        try:
            self.repo.git.add('.gitmodules')
        except Exception as e:
            raise RuntimeError(f"Failed to stage .gitmodules: {e}") from e

        try:
            self.repo.git.add(path)
        except Exception as e:
            raise RuntimeError(f"Failed to stage submodule path {path}: {e}") from e

    def remove_submodule(self, block: Dict[str, Any]) -> None:
        """Remove a submodule described by a parsed .gitmodules block.

        When a submodule matching the supplied `name` or `path` is
        found it will be removed via GitPython which handles deinit, removal of
        the gitlink, and cleanup of `.git/modules` when supported by the
        installed GitPython version.

        Args:
            block: dict-like parsed `.gitmodules` entry with at least `path` and
                optionally `name`.

        Raises:
            ValueError: if `path` is missing or the submodule cannot be found.
            RuntimeError: if GitPython/gitrepo operations fail.
        """
        name = block.get('name')
        path = block.get('path')

        if not path:
            raise ValueError("Invalid submodule block: missing path")

        if not name:
            raise ValueError("Invalid submodule block: missing name")

        # Lookup by name since paths can be duplicated across submodules
        try:
            submodule = self.repo.submodule(name)
            submodule_git_dir = self._get_submodule_git_dir(submodule)

            submodule.remove(force=False, module=True)
        except Exception as e:
            # TODO - .backup files can be proposed to be restored
            raise RuntimeError(f"Failed to remove submodule {name} at {path}: {e}") from e

        # Remove any remaining submodule path from the filesystem if it still exists
        # and is empty (no files inside). Extract root folder only.
        root_path = Path(path).parts[0] if Path(path).parts else path
        root_folder = self.repo_path / root_path
        if root_folder.exists() and root_folder.is_dir():
            try:
                # Only remove if directory is empty
                root_folder.rmdir()
            except OSError:
                # Directory not empty, leave it as is, may contain other submodules or user files
                pass

        # Stage .gitmodules if it still exists
        try:
            gm_path = self.repo_path / '.gitmodules'
            if gm_path.exists():
                self.repo.git.add('.gitmodules')
        except Exception as e:
            raise RuntimeError(
                f"Failed to stage .gitmodules after removing submodule {path}: {e}") from e

    def rebuild_submodule_metadata(self) -> None:
        """Rebuild .git metadata for all submodules based on .gitmodules.

        This method is destructive: it removes existing `.git/modules` data
        and may remove broken submodule working trees. It first creates a
        backup via `backup_submodule_metadata()` and attempts to restore on
        failure.
        """
        git_dir = Path(self.repo.git_dir)
        modules_dir = git_dir / 'modules'

        # Delete the 'modules' directory entirely if present
        try:
            if modules_dir.exists():
                shutil.rmtree(modules_dir, onerror=_remove_readonly)
        except (OSError, shutil.Error) as e:
            raise RuntimeError(f"Failed to delete modules directory {modules_dir}: {e}") from e

        # Remove any [submodule "..."] sections from .git/config
        config_path = git_dir / 'config'
        if config_path.exists():
            content = config_path.read_text()
            cleaned = re.sub(r'\[submodule "[^"]*"\][^\[]*', '', content)

            # only write if something changed
            if cleaned != content:
                config_path.write_text(cleaned)

        # Suppress all submodules
        # Collect all folders that have a .git FILE (submodule indicator)
        submodule_folders = [
            git_marker.parent
            for git_marker in self.repo_path.rglob('.git')
            if git_marker.is_file()  # .git file = submodule; .git dir = real repo root
        ]

        # Sort shallowest first: deleting a parent removes children automatically,
        # so we skip already-deleted nested paths with the exists() guard
        submodule_folders.sort(key=lambda p: len(p.parts))
        for folder in submodule_folders:
            if folder.exists() and folder != self.repo_path:
                shutil.rmtree(folder, onerror=_remove_readonly)

        # Init: registers submodules in .git/config (writes into main repo's
        # config via the gitfile)
        try:
            self.repo.git.submodule('init')
        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to init submodules: {e}") from e

        # Re-initialize and update all submodules to rebuild .git metadata
        try:
            self.repo.git.submodule('update', '--init', '--recursive', '--force')
        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to update submodules: {e}") from e

    def backup_submodule_metadata(self) -> None:
        """Backup .git metadata for all submodules."""
        git_dir = Path(self.repo.git_dir)

        # Backup modules folder
        modules_dir = git_dir / 'modules'
        backup_modules_dir = git_dir / 'modules.backup'
        try:
            if modules_dir.exists():
                if backup_modules_dir.exists():
                    shutil.rmtree(backup_modules_dir, onerror=_remove_readonly)
                shutil.copytree(modules_dir, backup_modules_dir, symlinks=True)
        except Exception as e:
            raise RuntimeError(
                f"Failed to backup modules directory {modules_dir} to {backup_modules_dir}: {e}") from e

        # Backup config
        config_path = git_dir / 'config'
        backup_config_path = git_dir / 'config.backup'
        try:
            if config_path.exists():
                shutil.copy2(config_path, backup_config_path)
        except Exception as e:
            raise RuntimeError(
                f"Failed to backup config file {config_path} to {backup_config_path}: {e}") from e

    def restore_submodule_metadata(self) -> None:
        """Restore .git metadata for all submodules from backup."""
        git_dir = Path(self.repo.git_dir)

        # Restore modules folder
        backup_modules_dir = git_dir / 'modules.backup'
        modules_dir = git_dir / 'modules'
        try:
            if backup_modules_dir.exists():
                if modules_dir.exists():
                    shutil.rmtree(modules_dir, onerror=_remove_readonly)
                shutil.copytree(backup_modules_dir, modules_dir, symlinks=True)
        except Exception as e:
            raise RuntimeError(
                f"Failed to restore modules directory from {backup_modules_dir} to {modules_dir}: {e}") from e

        # Restore config
        backup_config_path = git_dir / 'config.backup'
        config_path = git_dir / 'config'
        try:
            if backup_config_path.exists():
                shutil.copy2(backup_config_path, config_path)
        except Exception as e:
            raise RuntimeError(
                f"Failed to restore config file from {backup_config_path} to {config_path}: {e}") from e

    def _get_submodule_git_dir(self, submodule: Submodule) -> Path:
        """Return the git directory path. (.git folder)"""
        module_repo = submodule.module()
        git_dir = Path(module_repo.git_dir)

        if not git_dir.is_absolute():
            worktree_path = self.repo_path / submodule.path
            git_dir = (worktree_path / git_dir).resolve()

        return git_dir

    def move_submodule(self, name: str, new_path: str) -> None:
        """Move a submodule to a new path using `git mv` and update .gitmodules.

        This updates the `.gitmodules` entry for the given submodule name to the
        new path, performs a `git mv` to move the working tree and stage the
        change, and runs `git submodule sync` to ensure internal configuration
        is consistent.

        Args:
            name: the submodule name as recorded in .gitmodules
            new_path: the desired new path for the submodule inside the repo

        Raises:
            ValueError: if the named submodule cannot be found or destination exists
            RuntimeError: if the git operation fails
        """
        try:
            submodule = self.repo.submodule(name)
        except Exception as e:
            raise ValueError(f"Submodule not found: {name}") from e

        old_path = submodule.path
        if old_path == new_path:
            return

        dest = self.repo_path / new_path
        if dest.exists():
            raise ValueError(f"Destination path already exists: {new_path}")

        try:
            # Update .gitmodules to point to the new path
            self.repo.git.config('--file', '.gitmodules', f"submodule.{name}.path", new_path)
            try:
                self.repo.git.add('.gitmodules')
            except Exception:
                pass

            # Use git mv to move the working tree and stage the rename
            self.repo.git.mv(old_path, new_path)

            # Sync submodule configuration
            try:
                self.repo.git.submodule('sync', '--', name)
            except Exception:
                pass

        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to move submodule {name} to {new_path}: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to move submodule {name} to {new_path}: {e}") from e

    def clone_submodule(self, url: str, path: str, branch: str = "main") -> None:
        """Clone a submodule."""
        try:
            # Use git command to add submodule
            self.repo.git.submodule("add", "-b", branch, url, path)
        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to clone submodule {path}: {e}") from e

    def update_submodule(self, path: str, options: Dict[str, Any]) -> None:
        """Update a specific submodule."""
        try:
            if options.get("init", False):
                # Initialize and update submodule
                self.repo.git.submodule("update", "--init", "--recursive", path)
            else:
                # Just update existing submodules
                self.repo.git.submodule("update", "--recursive", path)

            if options.get("remote", False):
                # Update to latest on remote branch
                submodule_repo_path = self.repo_path / path
                if submodule_repo_path.exists():
                    submodule_repo = Repo(submodule_repo_path)
                    submodule_repo.remotes.origin.pull()

        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to update submodule {path}: {e}") from e
        except ValueError as e:
            raise ValueError(f"Submodule not found: {path}") from e

    def update_all_submodules(self, options: Dict[str, Any]) -> None:
        """Update all submodules."""
        for submodule in self.repo.submodules:
            self.update_submodule(submodule.path, options)

    def commit_all(self, message: str) -> None:
        """Commit all changes recursively, deepest submodules first."""
        try:
            pending_submodules = []
            for submodule in self.repo.submodules:
                if not submodule.module_exists():
                    continue

                submodule_repo = submodule.module()
                if submodule_repo.is_dirty() or submodule_repo.untracked_files:
                    pending_submodules.append(
                        (len(Path(submodule.path).parts), submodule, submodule_repo))

            for _, submodule, submodule_repo in sorted(
                pending_submodules,
                key=lambda item: item[0],
                reverse=True,
            ):
                submodule_repo.git.add(all=True)
                submodule_repo.index.commit(f"Update {submodule.name}: {message}")

            # Stage and commit the main repository last so the submodule gitlinks
            # are included once the nested submodule commits have been recorded.
            self.repo.git.add(all=True)
            if self.repo.is_dirty() or self.repo.untracked_files:
                self.repo.index.commit(message)
            else:
                raise ValueError("No changes to commit")

        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to commit changes: {e}") from e

    def push_all(self) -> None:
        """Push all commits to remote."""
        try:
            # Push main repository
            origin = self.repo.remote('origin')
            origin.push()

            # Push all submodules
            for submodule in self.repo.submodules:
                if submodule.module_exists():
                    submodule_repo = submodule.module()
                    try:
                        submodule_origin = submodule_repo.remote('origin')
                        submodule_origin.push()
                    except (git.GitCommandError, ValueError):
                        # Skip if submodule has no remote or push fails
                        pass

        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to push changes: {e}") from e
        except ValueError as e:
            raise RuntimeError(f"No remote origin configured: {e}") from e

    def get_status(self) -> Dict[str, Any]:
        """Get repository status."""
        return {
            "is_dirty": self.repo.is_dirty(),
            "untracked_files": self.repo.untracked_files,
            "modified_files": [item.a_path for item in self.repo.index.diff(None)],
            "staged_files": [item.a_path for item in self.repo.index.diff("HEAD")],
        }


class OrderedGitConfigParser(GitConfigParser):
    """GitConfigParser with ordered field writing"""

    # Standard Git field order
    DEFAULT_FIELD_ORDER = [
        'path',                      # Required
        'url',                       # Required
        'branch',                    # Optional
        'update',                    # Optional
        'fetchRecurseSubmodules',    # Optional
        'ignore',                    # Optional
        'shallow',                   # Optional
        'active'                     # Optional
    ]

    def __init__(self, file_or_files, read_only=False, field_order=None):
        super().__init__(file_or_files, read_only=read_only)
        self.field_order = field_order or self.DEFAULT_FIELD_ORDER

    def write(self, fp=None):
        """Write config with ordered fields"""
        should_close = False

        if fp is None:
            fp = open(self._file_or_files, 'w')
            should_close = True

        try:
            self._write_ordered(fp)
        except IOError as e:
            raise IOError(f"Failed to write config file: {e}") from e
        finally:
            if should_close:
                fp.close()

    def _write_ordered(self, fp):
        """Write sections with ordered fields"""
        all_sections = [s for s in self._sections.keys() if s != 'DEFAULT']

        for i, section in enumerate(all_sections):
            fp.write(f"[{section}]\n")

            section_dict = self._sections[section]

            # Write fields in order
            for field in self.field_order:
                if field in section_dict and field != '__name__':
                    value = section_dict[field]
                    fp.write(f"\t{field} = {value}\n")

            # Write any fields not in field_order
            for key, value in section_dict.items():
                if key not in self.field_order and key != '__name__':
                    fp.write(f"\t{key} = {value}\n")
