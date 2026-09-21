"""Test manager.py"""
import unittest

from yagso.domain.bom import Bom
from yagso.domain.manifest import Manifest
from yagso.infrastructure.manifest_manager import ManifestManager

# pylint: disable=all


class TestGetSubmoduleFieldMerged(unittest.TestCase):

    def setUp(self):
        self.manager = ManifestManager()

    def _manifest_dict(self):
        return {
            "version": "1.1",
            "submodules": [{
                "name": "lib1",
                "path": "lib1",
                "url": "https://github.com/a/b.git",
                "commit": "c1111111111111111111111111111111111111111",
            }],
        }

    def test_get_from_manifest(self):
        manifest = Manifest.from_dict(self._manifest_dict())
        self.assertEqual(
            self.manager.get_submodule_field(manifest, "lib1", "commit"),
            "c1111111111111111111111111111111111111111")

    def test_get_from_bom(self):
        bom = Bom.from_dict({
            "version": "1.0",
            "submodules": [{
                "path": "lib1",
                "commit": "c1111111111111111111111111111111111111111",
                "files": ["a.c"],
            }],
        })
        self.assertEqual(
            self.manager.get_submodule_field(bom, "lib1", "files"), ["a.c"])

    def test_missing_submodule_raises_filenotfound(self):
        manifest = Manifest.from_dict(self._manifest_dict())
        with self.assertRaises(FileNotFoundError):
            self.manager.get_submodule_field(manifest, "nope", "commit")

    def test_invalid_field_raises_valueerror(self):
        manifest = Manifest.from_dict(self._manifest_dict())
        with self.assertRaises(ValueError):
            self.manager.get_submodule_field(manifest, "lib1", "no_such_field")

    def test_nested_lookup(self):
        data = self._manifest_dict()
        data["submodules"][0]["submodules"] = [{
            "name": "inner",
            "path": "inner",
            "url": "https://github.com/a/c.git",
            "commit": "c3333333333333333333333333333333333333333",
        }]
        manifest = Manifest.from_dict(data)
        self.assertEqual(
            self.manager.get_submodule_field(manifest, "lib1/inner", "name"),
            "inner")


if __name__ == "__main__":
    unittest.main()
