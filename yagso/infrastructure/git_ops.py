"""Infrastructure layer for Git operations using gitpython."""

from pathlib import Path
from typing import Dict, List, Any, Optional
import re
import git
from git import Repo, Submodule

from ..domain.submodule import SubmoduleDefinition


class GitOperations:
    """Interface to Git commands using gitpython."""

    def __init__(self, repo_path: Path):
        """Initialize with repository path."""
        self.repo_path = repo_path
        self._repo: Optional[Repo] = None

    @property
    def repo(self) -> Repo:
        """Get or create GitPython Repo object."""
        if self._repo is None:
            try:
                self._repo = Repo(self.repo_path)
            except git.InvalidGitRepositoryError:
                raise ValueError(f"Not a valid Git repository: {self.repo_path}")
        return self._repo

    def get_recorded_commit(self, path: str) -> Optional[str]:
        """Return the commit SHA recorded in HEAD for the gitlink at `path`.

        Uses git ls-tree to read the tree entry for the path and extracts the commit hash.
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
        """Return a list of refs (local branches, tags, and remote branches/tags)
        in the worktree at `worktree_path` that contain `commit`.

        Excludes symbolic `HEAD` refs (e.g. `HEAD` or `origin/HEAD`). If the
        worktree is not a git repository or the command fails, returns an empty list.
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
        """List all submodules in the repository."""
        submodules = []
        for submodule in self.repo.submodules:
            try:
                # This reads from .gitmodules without defaults
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

    def is_git_repository(self) -> bool:
        """Check if the path is a valid Git repository."""
        try:
            Repo(self.repo_path)
            return True
        except git.InvalidGitRepositoryError:
            return False

    def sync_submodule(self, submodule_def: SubmoduleDefinition) -> None:
        """Ensure local submodule matches the provided SubmoduleDefinition.

        This will:
        - Add the submodule if missing.
        - Update .gitmodules/.git/config if URL or branch differ.
        - Initialize/update the worktree for the submodule.
        - Checkout the requested commit/branch/tag/hash in the submodule.
        - Stage any changes to `.gitmodules` and the submodule gitlink in the superproject.
        """
        name = submodule_def.name
        path = submodule_def.path
        url = submodule_def.url
        desired_commit = submodule_def.commit
        desired_branch = submodule_def.tracking_branch

        # Find existing submodule entry (if any). If .gitmodules is malformed
        # attempting to access repo.submodules may raise; treat that as no existing
        existing = None
        try:
            for s in self.repo.submodules:
                if s.path == path or s.name == name:
                    existing = s
                    break
        except Exception:
            existing = None

        try:
            # If submodule definition doesn't exist in .gitmodules, add it
            if existing is None:
                # Use provided branch if any, otherwise let git choose
                branch_arg = desired_branch if desired_branch else "main"

                sub_path_fs = self.repo_path / path
                try:
                    if sub_path_fs.exists():
                        # Path exists on disk; try to add and force if necessary
                        try:
                            self.repo.git.submodule('add', '--force', '-b', branch_arg, url, path)
                        except git.GitCommandError as e:
                            # If add fails because the path exists in index, try to write
                            # .gitmodules
                            try:
                                self.repo.git.config(
                                    '--file', '.gitmodules', f"submodule.{name}.url", url)
                                if desired_branch:
                                    self.repo.git.config(
                                        '--file', '.gitmodules', f"submodule.{name}.branch", desired_branch)
                                self.repo.git.submodule('sync', '--', path)
                                self.repo.git.submodule('update', '--init', '--recursive', path)
                            except Exception:
                                raise RuntimeError(f"Failed to clone submodule {path}: {e}")
                    else:
                        self.clone_submodule(url, path, branch_arg)

                    # Stage .gitmodules if present
                    try:
                        self.repo.git.add('.gitmodules')
                    except Exception:
                        pass

                    # Initialize the working copy
                    self.repo.git.submodule('update', '--init', '--recursive', path)
                    existing = next((s for s in self.repo.submodules if s.path == path), None)
                except Exception as e:
                    raise RuntimeError(f"Failed to add or init submodule {path}: {e}")

            # Ensure .gitmodules has a path entry for this submodule (some git operations
            # may create a section without path; fix it up so later config reads succeed)
            try:
                cur_path = None
                try:
                    cur_path = self.repo.git.config(
                        '--file', '.gitmodules', '--get', f"submodule.{name}.path")
                except git.GitCommandError:
                    cur_path = None

                if not cur_path:
                    try:
                        self.repo.git.config(
                            '--file', '.gitmodules', f"submodule.{name}.path", path)
                        try:
                            self.repo.git.add('.gitmodules')
                        except Exception:
                            pass
                    except Exception:
                        # non-fatal
                        pass
            except Exception:
                pass

            # If url differs, update .gitmodules and sync
            if existing is not None and getattr(existing, 'url', None) != url:
                # Update .gitmodules entry
                try:
                    self.repo.git.config('--file', '.gitmodules', f"submodule.{name}.url", url)
                except git.GitCommandError:
                    # fallback to submodule set-url if available
                    try:
                        self.repo.git.submodule('set-url', path, url)
                    except Exception:
                        pass

                # Sync to update .git/config
                try:
                    self.repo.git.submodule('sync', '--', path)
                except Exception:
                    pass

                try:
                    self.repo.git.add('.gitmodules')
                except Exception:
                    pass

            # If branch differs, update .gitmodules branch config
            if desired_branch:
                try:
                    self.repo.git.config(
                        '--file',
                        '.gitmodules',
                        f"submodule.{name}.branch",
                        desired_branch)
                    self.repo.git.submodule('sync', '--', path)
                    try:
                        self.repo.git.add('.gitmodules')
                    except Exception:
                        pass
                except Exception:
                    # non-fatal: continue
                    pass

            # Ensure worktree exists for the submodule
            submodule_repo_path = self.repo_path / path
            try:
                sub_repo = Repo(submodule_repo_path)
            except git.InvalidGitRepositoryError:
                # Initialize/update working copy
                try:
                    self.repo.git.submodule('update', '--init', '--recursive', path)
                except Exception as e:
                    raise RuntimeError(f"Failed to init submodule {path}: {e}")
                try:
                    sub_repo = Repo(submodule_repo_path)
                except git.InvalidGitRepositoryError as e:
                    raise RuntimeError(
                        f"Submodule repository not found at {submodule_repo_path}: {e}")

            # Fetch remote refs to be able to resolve branches/tags
            try:
                if 'origin' in [r.name for r in sub_repo.remotes]:
                    sub_repo.remotes.origin.fetch('--tags')
                else:
                    # attempt a generic fetch
                    sub_repo.git.fetch('--all')
            except Exception:
                # Non-fatal; later operations may still succeed
                pass

            # Resolve desired commit/branch/tag to a commit-ish
            resolved = None
            try:
                resolved = sub_repo.git.rev_parse(desired_commit)
            except Exception:
                # Try fetching more aggressively then resolve
                try:
                    sub_repo.git.fetch('--all')
                    sub_repo.git.fetch('--tags')
                    resolved = sub_repo.git.rev_parse(desired_commit)
                except Exception:
                    resolved = None

            if resolved is None:
                # As a last resort try to see if remote has the ref
                try:
                    out = sub_repo.git.ls_remote('origin', desired_commit)
                    if out:
                        # ls-remote returns lines like '<sha>\trefs/...'
                        first = out.splitlines()[0]
                        resolved = first.split('\t', 1)[0]
                except Exception:
                    resolved = None

            if resolved is None:
                raise RuntimeError(
                    f"Cannot resolve commit/branch/tag '{desired_commit}' for submodule {name}")

            # Checkout resolved ref. If desired_commit looks like a branch name and
            # origin/<branch> exists, create local branch tracking it.
            try:
                # If it's a full SHA, just checkout (detached)
                if re.fullmatch(r"[0-9a-fA-F]{7,40}", desired_commit):
                    sub_repo.git.checkout(resolved)
                else:
                    # Try to check out a branch tracking origin/<desired_commit> if present
                    origin_ref = f"origin/{desired_commit}"
                    refs = [r.name for r in sub_repo.refs]
                    if origin_ref in refs:
                        # create or reset local branch to track remote
                        try:
                            sub_repo.git.checkout('-B', desired_commit, origin_ref)
                        except Exception:
                            sub_repo.git.checkout(desired_commit)
                    else:
                        # fallback to checking out the name (could be tag or local branch)
                        sub_repo.git.checkout(desired_commit)
            except git.GitCommandError as e:
                # If checkout by name failed, attempt to checkout by resolved sha
                try:
                    sub_repo.git.checkout(resolved)
                except Exception:
                    raise RuntimeError(
                        f"Failed to checkout '{desired_commit}' in submodule {name}: {e}")

            # Stage the submodule gitlink change in the superproject
            try:
                self.repo.git.add(path)
            except Exception:
                # fallback to index add
                try:
                    self.repo.index.add([path])
                except Exception:
                    pass

        except Exception as e:
            raise RuntimeError(f"Failed to sync submodule {name}: {e}")
