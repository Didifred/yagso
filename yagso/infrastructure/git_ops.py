"""Infrastructure layer for Git operations using gitpython."""

from pathlib import Path
from typing import Dict, List, Any, Optional
import re
from git import Repo, Submodule, Git

from ..domain.submodule import SubmoduleDefinition


class GitOperations:
    """Interface to Git commands using gitpython."""

    def is_same_repo(url1: str, url2: str) -> bool:
        """Check if two repo URLs point to same repository by comparing HEAD."""
        g = Git()
        try:
            head1 = g.ls_remote(url1, 'HEAD').split()[0]
            head2 = g.ls_remote(url2, 'HEAD').split()[0]
            return head1 == head2
        except BaseException:
            return False

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

    def read_gitmodules_blocks(self) -> list:
        """Return parsed submodule blocks using GitPython.

        Uses `self.get_submodules()` to obtain submodule entries and
        converts them to the same simple block dict format previously
        produced by parsing the .gitmodules file.
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
        - Change name if differ.
        - Change tracking branch if differ.
        - Checkout the requested commit/branch/tag/hash in the submodule.
        - Stage any changes to `.gitmodules` and the submodule gitlink in the superproject.
        """
        try:
            submodule = self.repo.submodule(submodule_def.path)

            reader = submodule.config_reader()

            # Update name if it differs
            current_name = None
            try:
                current_name = reader.get_value('name')
            except Exception:
                pass

            if current_name != submodule_def.name:
                self.repo.git.submodule("set-name", submodule_def.name, submodule_def.path)

            # Update URL if it differs (handle https <-> ssh changes)
            current_url = None
            try:
                current_url = reader.get_value('url')
            except Exception:
                pass

            if current_url != submodule_def.url:
                try:
                    self.repo.git.config(
                        '--file',
                        '.gitmodules',
                        f"submodule.{
                            submodule_def.name}.url",
                        submodule_def.url)
                except git.GitCommandError:
                    pass

                try:
                    self.repo.git.add('.gitmodules')
                except Exception:
                    pass

                try:
                    self.repo.git.submodule('sync', '--', submodule_def.path)
                except Exception:
                    pass

            # Update tracking branch if it differs
            current_branch = None
            try:
                current_branch = reader.get_value('branch')
            except Exception:
                pass  # No branch key in .gitmodules

            if current_branch != submodule_def.tracking_branch:
                if submodule_def.tracking_branch:
                    self.repo.git.submodule(
                        "set-branch",
                        "--branch",
                        submodule_def.tracking_branch,
                        submodule_def.path)
                else:
                    # Unset branch if tracking_branch is None or empty
                    self.repo.git.submodule("set-branch", "--unset", submodule_def.path)

            # Checkout the requested commit/branch/tag/hash in the submodule
            sub_repo_path = self.repo_path / submodule_def.path
            if not sub_repo_path.exists():
                raise ValueError(f"Submodule path does not exist: {sub_repo_path}")

            sub_repo = Repo(sub_repo_path)
            try:
                # Try to checkout the commit directly (if it's a SHA or tag)
                sub_repo.git.checkout(submodule_def.commit)
            except git.GitCommandError:
                # If that fails, try to checkout the tracking branch (if specified)
                if submodule_def.tracking_branch:
                    sub_repo.git.checkout(submodule_def.tracking_branch)
                else:
                    raise RuntimeError(
                        f"Failed to checkout commit {
                            submodule_def.commit} and no tracking branch specified for {
                            submodule_def.name}")

        except ValueError as e:
            raise ValueError(f"Submodule not found: {submodule_def.path}")
        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to sync submodule {submodule_def.name}: {e}")

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
