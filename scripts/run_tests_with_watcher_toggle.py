#!/usr/bin/env python3
"""Add or remove specific `files.watcherExclude` entries in .vscode/settings.json.

Usage:
    python scripts/run_tests_with_watcher_toggle.py add
    python scripts/run_tests_with_watcher_toggle.py remove
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Iterable


def find_settings_path() -> Path | None:
    here = Path(__file__).resolve()
    for p in (here, *here.parents):
        candidate = p / ".vscode" / "settings.json"
        if candidate.exists():
            return candidate
    cwd_candidate = Path.cwd() / ".vscode" / "settings.json"
    if cwd_candidate.exists():
        return cwd_candidate
    return None


def load_settings(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_settings(path: Path, data: Dict[str, Any]) -> None:
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


def add_keys(settings: Dict[str, Any], keys: Iterable[str]) -> Dict[str, Any]:
    watcher = settings.setdefault("files.watcherExclude", {})
    changed: Dict[str, Any] = {}
    for k in keys:
        prev = watcher.get(k, None)
        if prev is not True:
            watcher[k] = True
            changed[k] = prev
    return changed


def remove_keys(settings: Dict[str, Any], keys: Iterable[str]) -> Dict[str, Any]:
    watcher = settings.get("files.watcherExclude", {})
    removed: Dict[str, Any] = {}
    for k in keys:
        if k in watcher:
            removed[k] = watcher.pop(k)

    # remove watcher key if empty
    if not settings.get("files.watcherExclude"):
        settings.pop("files.watcherExclude", None)

    return removed


def add_watcherExclude():
    settings_path = find_settings_path()
    if not settings_path or not settings_path.exists():
        print("No .vscode/settings.json found. Exiting.")
        sys.exit(1)

    try:
        settings = load_settings(settings_path)
    except Exception as e:
        print(f"Failed to load {settings_path}: {e}")
        sys.exit(1)

    changed = add_keys(settings, KEYS)
    if not changed:
        print("No changes needed; keys already set to true.")
    else:
        print("Will set the following keys to true:")
        for k, prev in changed.items():
            print(f"  {k}: was {prev}")

    try:
        save_settings(settings_path, settings)
    except Exception as e:
        print(f"Failed to write {settings_path}: {e}")
        sys.exit(1)

    print(f"Updated {settings_path} with watcherExclude keys.")


def remove_watcherExclude():
    settings_path = find_settings_path()
    if not settings_path or not settings_path.exists():
        print("No .vscode/settings.json found. Exiting.")
        sys.exit(1)

    try:
        settings = load_settings(settings_path)
    except Exception as e:
        print(f"Failed to load {settings_path}: {e}")
        sys.exit(1)

    removed = remove_keys(settings, KEYS)
    if not removed:
        print("No keys removed; none were present.")
    else:
        print("Will remove the following keys:")
        for k, prev in removed.items():
            print(f"  {k}: was {prev}")

    try:
        save_settings(settings_path, settings)
    except Exception as e:
        print(f"Failed to write {settings_path}: {e}")
        sys.exit(1)

    print(f"Updated {settings_path} by removing watcherExclude keys.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add or remove watcher-exclude keys in VS Code settings.")
    parser.add_argument("action", choices=("add", "remove"), help="Action to perform")
    args = parser.parse_args()

    if args.action == "add":
        add_watcherExclude()
    elif args.action == "remove":
        remove_watcherExclude()


if __name__ == "__main__":
    main()
