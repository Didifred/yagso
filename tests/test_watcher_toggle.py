import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.watcher_toggle import WatcherToggle


class TestWatcherToggle(unittest.TestCase):
    def test_add_and_remove_watcher_excludes(self):

        toggle = WatcherToggle()

        toggle.add_watcherExclude()

        settings_path = toggle._find_settings_path()
        self.assertIsNotNone(settings_path)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIn("files.watcherExclude", settings)
        self.assertTrue(settings["files.watcherExclude"].get("**/tests/**/yagso_test_root/**"))

        toggle.remove_watcherExclude()

        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertNotIn("files.watcherExclude", settings)
