"""Infrastructure layer for Git operations using gitpython."""
import re
import git
from pathlib import Path
from collections import OrderedDict
from typing import Dict, List, Any, Optional
from git import Repo, Submodule, Git
from git.config import GitConfigParser
from ..domain.submodule import SubmoduleDefinition


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
            except git.InvalidGitRepositoryError:
                raise ValueError(f"Not a valid Git repository: {self.repo_path}")

        return self._repo

    def close(self) -> None:
        """Release internal Repo reference to allow deterministic cleanup.

        Setting ``self._repo`` to ``None`` removes the reference to the
        GitPython ``Repo`` instance so it can be garbage-collected before
        interpreter shutdown (helps avoid shutdown-time destructor races
        on Windows).
        """
        try:
            self._repo = None
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self._repo = None
        except Exception:
            pass
        return False

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
            raise IOError(f"Failed to read submodules via GitPython: {e}")

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
            except IOError:
                raise RuntimeError(f".submodule read error: {submodule_def.path}")

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
            desired_commit = submodule_def.commit

            # Only attempt resolution/checkout when a desired ref is provided
            if desired_commit:
                sub_repo = Repo(sub_repo_path)

                try:
                    resolved_sha = sub_repo.git.rev_parse(desired_commit)
                except Exception as e:
                    resolved_sha = None
                    raise RuntimeError(
                        f"Failed to resolve sha of {desired_commit} in submodule {
                            submodule_def.name}: {e}")
                # TODO - Maybe checkout also if commit field is a branch even if equal
                if not GitOperations.sha_equal(current_commit, resolved_sha):
                    try:
                        sub_repo.git.checkout(desired_commit)
                    except Exception as e:
                        raise RuntimeError(
                            f"Failed to checkout {desired_commit} in submodule {
                                submodule_def.name}: {e}")

        except ValueError as e:
            raise ValueError(f"Submodule not found: {submodule_def.path} : {e}")
        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to sync submodule {submodule_def.name}: {e}")
        except git.exc.InvalidGitRepositoryError as e:
            raise RuntimeError(f"Submodule repository error for {submodule_def.path}: {e}")

    # NOT YET TESTED METHODS BELOW (TODO: add tests for these)
    def add_submodule(self, submodule_def: SubmoduleDefinition) -> None:
        """Add a new submodule according to the SubmoduleDefinition.

        This will add an entry to `.gitmodules`, initialize the submodule
        worktree, checkout the requested commit/branch/tag, and stage changes.
        """
        name = submodule_def.name
        path = submodule_def.path
        url = submodule_def.url
        desired_branch = submodule_def.tracking_branch
        desired_commit = submodule_def.commit

        # If an entry already exists, treat as sync instead
        try:
            # Use git submodule add (this will update .gitmodules)
            branch_arg = desired_branch if desired_branch else "main"
            try:
                self.clone_submodule(url, path, branch_arg)
            except RuntimeError:
                # Fallback: write .gitmodules directly and sync
                try:
                    self.repo.git.config('--file', '.gitmodules', f"submodule.{name}.path", path)
                    self.repo.git.config('--file', '.gitmodules', f"submodule.{name}.url", url)
                    if desired_branch:
                        self.repo.git.config(
                            '--file',
                            '.gitmodules',
                            f"submodule.{name}.branch",
                            desired_branch)
                    try:
                        self.repo.git.add('.gitmodules')
                    except Exception:
                        pass
                    self.repo.git.submodule('sync', '--', path)
                except Exception as e:
                    raise RuntimeError(f"Failed to add submodule {name}: {e}")

            # Initialize and update working copy
            try:
                self.repo.git.submodule('update', '--init', '--recursive', path)
            except Exception:
                pass

            # Checkout desired commit/branch inside submodule
            sub_repo_path = self.repo_path / path
            if sub_repo_path.exists():
                try:
                    sub_repo = Repo(sub_repo_path)
                except git.InvalidGitRepositoryError:
                    raise RuntimeError(f"Added submodule but repository missing at {sub_repo_path}")

                # Try to resolve and checkout the desired commit/branch/tag
                resolved = None
                try:
                    resolved = sub_repo.git.rev_parse(desired_commit)
                except Exception:
                    try:
                        sub_repo.remotes.origin.fetch('--tags')
                        sub_repo.git.fetch('--all')
                        resolved = sub_repo.git.rev_parse(desired_commit)
                    except Exception:
                        resolved = None

                if resolved:
                    try:
                        sub_repo.git.checkout(resolved)
                    except Exception:
                        try:
                            sub_repo.git.checkout(desired_commit)
                        except Exception:
                            pass
                else:
                    # Try checkout by branch name
                    if desired_branch:
                        try:
                            sub_repo.git.checkout('-B', desired_branch, f'origin/{desired_branch}')
                        except Exception:
                            try:
                                sub_repo.git.checkout(desired_branch)
                            except Exception:
                                pass

            # Stage .gitmodules and the gitlink
            try:
                self.repo.git.add('.gitmodules')
            except Exception:
                pass

            try:
                self.repo.git.add(path)
            except Exception:
                try:
                    self.repo.index.add([path])
                except Exception:
                    pass

        except Exception as e:
            raise RuntimeError(f"Failed to add submodule {name}: {e}")

    def remove_submodule(self, block: Dict[str, Any]) -> None:
        """Remove a submodule described by a parsed .gitmodules block.

        This will deinitialize the submodule, remove the .gitmodules section,
        remove the gitlink from the index and delete the worktree directory.
        Changes are staged where applicable.
        """
        name = block.get('name')
        path = block.get('path')

        if not path:
            raise ValueError("Invalid submodule block: missing path")

        try:
            # Deinit the submodule (remove worktree/links)
            try:
                self.repo.git.submodule('deinit', '-f', '--', path)
            except Exception:
                pass

            # Remove section from .gitmodules if present
            gm_path = self.repo_path / '.gitmodules'
            if gm_path.exists():
                try:
                    if name:
                        # Try using git config to remove the section
                        try:
                            self.repo.git.config(
                                '--file', '.gitmodules', '--remove-section', f"submodule.{name}")
                        except git.GitCommandError:
                            # Fallback to manual removal
                            content = gm_path.read_text()
                            pattern = re.compile(
                                r'\[submodule\s+"' + re.escape(name) + r'"\][^\[]*', re.M)
                            new = pattern.sub('', content)
                            gm_path.write_text(new)
                    else:
                        # No name provided: remove by matching path entry
                        content = gm_path.read_text()
                        # Find any section that contains 'path = <path>'
                        pattern = re.compile(
                            r'\[submodule\s+"([^"]+)"\]([^\[]*path\s*=\s*' + re.escape(path) + r'[^\[]*)', re.M)
                        new = pattern.sub('', content)
                        gm_path.write_text(new)

                    try:
                        self.repo.git.add('.gitmodules')
                    except Exception:
                        pass
                except Exception:
                    pass

            # Remove gitlink from index (stage deletion)
            try:
                self.repo.git.rm('-f', '--cached', '-r', path)
            except Exception:
                try:
                    self.repo.index.remove([path], r=True)
                except Exception:
                    pass

            # Remove the submodule worktree directory from filesystem
            sub_path = self.repo_path / path
            try:
                if sub_path.exists():
                    # Use shutil to remove tree safely
                    import shutil
                    shutil.rmtree(sub_path)
            except Exception:
                pass

        except Exception as e:
            raise RuntimeError(f"Failed to remove submodule {path}: {e}")

    def clone_submodule(self, url: str, path: str, branch: str = "main") -> None:
        """Clone a submodule."""
        try:
            # Use git command to add submodule
            self.repo.git.submodule("add", "-b", branch, url, path)
        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to clone submodule {path}: {e}")

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
            raise RuntimeError(f"Failed to update submodule {path}: {e}")
        except ValueError:
            raise ValueError(f"Submodule not found: {path}")

    def update_all_submodules(self, options: Dict[str, Any]) -> None:
        """Update all submodules."""
        for submodule in self.repo.submodules:
            self.update_submodule(submodule.path, options)

    def commit_all(self, message: str) -> None:
        """Commit all changes recursively."""
        try:
            # Add all changes in main repo
            self.repo.git.add(all=True)

            # Commit if there are changes
            if self.repo.is_dirty() or self.repo.untracked_files:
                self.repo.index.commit(message)
            else:
                raise ValueError("No changes to commit")

            # Also commit in submodules if they have changes
            for submodule in self.repo.submodules:
                if submodule.module_exists():
                    submodule_repo = submodule.module()
                    if submodule_repo.is_dirty() or submodule_repo.untracked_files:
                        submodule_repo.git.add(all=True)
                        submodule_repo.index.commit(f"Update {submodule.name}: {message}")

        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to commit changes: {e}")

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
            raise RuntimeError(f"Failed to push changes: {e}")
        except ValueError as e:
            raise RuntimeError(f"No remote origin configured: {e}")

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
            raise IOError(f"Failed to write config file: {e}")
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

            # Blank line between sections (except last)
            if i < len(all_sections) - 1:
                fp.write("\n")
