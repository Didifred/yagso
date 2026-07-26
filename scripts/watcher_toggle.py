"""Add or remove specific `files.watcherExclude` entries in .vscode/settings.json.
    add_watcherExclude() - Adds the following keys to `files.watcherExclude` in .vscode/settings.json:
        "**/tests/**/yagso_test_root/**"
    remove_watcherExclude() - Removes the above keys from `files.watcherExclude` in .vscode/settings.json.
    If .vscode/settings.json does not exist, the functions will print a message and exit with a non-zero status code.

"""

from __future__ import annotations

import json
import os
import git
from pathlib import Path
from typing import Dict, Any, Iterable


class WatcherToggle:

    def _find_settings_path(self) -> Path | None:
        here = Path(__file__).resolve()
        for p in (here, *here.parents):
            candidate = p / ".vscode" / "settings.json"
            if candidate.exists():
                return candidate
        cwd_candidate = Path.cwd() / ".vscode" / "settings.json"
        if cwd_candidate.exists():
            return cwd_candidate
        return None

    def _load_settings(self, path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _save_settings(self, path: Path, data: Dict[str, Any]) -> None:
        tmp = path.with_suffix(".tmp")
        # Write to a temp file, flush and fsync to ensure data reaches disk,
        # then atomically replace the target settings file.
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.write("\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                # If fsync isn't available or fails, ignore and continue.
                pass
        tmp.replace(path)

    KEYS = ["**/tests/**/yagso_test_root/**", "**/.git/**"]

    def _add_keys(self, settings: Dict[str, Any], keys: Iterable[str]) -> Dict[str, Any]:
        watcher = settings.setdefault("files.watcherExclude", {})
        changed: Dict[str, Any] = {}
        for k in keys:
            prev = watcher.get(k, None)
            if prev is not True:
                watcher[k] = True
                changed[k] = prev
        return changed

    def _remove_keys(self, settings: Dict[str, Any], keys: Iterable[str]) -> Dict[str, Any]:
        watcher = settings.get("files.watcherExclude", {})
        removed: Dict[str, Any] = {}
        for k in keys:
            if k in watcher:
                removed[k] = watcher.pop(k)

        # remove watcher key if empty
        if not settings.get("files.watcherExclude"):
            settings.pop("files.watcherExclude", None)

        return removed

    def add_watcherExclude(self):
        settings_path = self._find_settings_path()
        if not settings_path or not settings_path.exists():
            print("No .vscode/settings.json found. Exiting.")
            return

        try:
            settings = self._load_settings(settings_path)
        except Exception as e:
            print(f"Failed to load {settings_path}: {e}")
            return

        changed = self._add_keys(settings, self.KEYS)
        if not changed:
            print("No changes needed; keys already set to true.")
        else:
            print("Will set the following keys to true:")
            for k, prev in changed.items():
                print(f"  {k}: was {prev}")

        try:
            self._save_settings(settings_path, settings)
        except Exception as e:
            print(f"Failed to write {settings_path}: {e}")

        print(f"Updated {settings_path} with watcherExclude keys.")

    def remove_watcherExclude(self):
        settings_path = self._find_settings_path()
        if not settings_path or not settings_path.exists():
            print("No .vscode/settings.json found. Exiting.")
            return

        try:
            settings = self._load_settings(settings_path)
        except Exception as e:
            print(f"Failed to load {settings_path}: {e}")
            return

        removed = self._remove_keys(settings, self.KEYS)
        if not removed:
            print("No keys removed; none were present.")
        else:
            print("Will remove the following keys:")
            for k, prev in removed.items():
                print(f"  {k}: was {prev}")

        try:
            self._save_settings(settings_path, settings)
        except Exception as e:
            print(f"Failed to write {settings_path}: {e}")

        print(f"Updated {settings_path} by removing watcherExclude keys.")

    def refresh_all_scm(self, path: Path) -> None:
        """Refresh VS Code SCM for root repo and all submodules."""
        try:
            repo = git.Repo(path)
        except (git.InvalidGitRepositoryError, Exception):
            return

        self._refresh_scm(repo)  # Refresh root repo

    def _refresh_scm(self, repo: git.Repo) -> None:
        """Refresh the SCM index for a repository and its submodules."""

        for sm in repo.submodules:
            try:
                self._refresh_scm(sm.module())
            except Exception as exc:
                print(f"[SCM] failed to refresh submodule {sm.path}: {exc}")
                pass

        try:
            repo.git.update_index("--refresh", with_exceptions=False)
            print(f"[SCM] refreshed → {repo.working_dir}")
        except Exception as exc:
            print(f"[SCM] failed to refresh {repo.working_dir}: {exc}")
            return
