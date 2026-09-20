import unittest
from pathlib import Path
from unittest.mock import patch

from yagso.core.orchestrator import SubmoduleOrchestrator, DiffStatus
from yagso.domain.submodule import SubmoduleDefinition
from tests.common import BaseGitTest


def _sub(name="lib1", path="lib1", url="https://github.com/a/b.git",
         commit="c1111111111111111111111111111111111111111", branch=None):
    return SubmoduleDefinition(
        root_path=path,
        name=name,
        path=path,
        url=url,
        commit=commit,
        tracking_branch=branch,
    )


def _block(name="lib1", path="lib1", url="https://github.com/a/b.git",
           commit="c1111111111111111111111111111111111111111", branch=None):
    block = {"name": name, "path": path, "url": url, "commit": commit}
    if branch:
        block["branch"] = branch
    return block


class TestSearchSubmodule(unittest.TestCase):

    def setUp(self):
        self.orch = SubmoduleOrchestrator(Path("."))

    def test_unchanged(self):
        blocks = [_block()]
        result = self.orch._search_submodule(_sub(), blocks)
        self.assertEqual(result.status, DiffStatus.UNCHANGED)
        self.assertEqual(result.name, "lib1")
        self.assertEqual(result.block["path"], "lib1")
        self.assertEqual(blocks, [])

    def test_modified_commit(self):
        blocks = [_block(commit="c2222222222222222222222222222222222222222")]
        result = self.orch._search_submodule(_sub(), blocks)
        self.assertEqual(result.status, DiffStatus.MODIFIED)
        self.assertEqual(blocks, [])

    def test_modified_name(self):
        blocks = [_block(name="other")]
        result = self.orch._search_submodule(_sub(), blocks)
        self.assertEqual(result.status, DiffStatus.MODIFIED)
        self.assertEqual(blocks, [])

    def test_modified_branch(self):
        blocks = [_block(branch="develop")]
        result = self.orch._search_submodule(_sub(branch="main"), blocks)
        self.assertEqual(result.status, DiffStatus.MODIFIED)
        self.assertEqual(blocks, [])

    def test_url_change_same_repo(self):
        blocks = [_block(url="git@github.com:a/b.git")]
        with patch("yagso.core.orchestrator.GitOperations.is_same_repo",
                   return_value=True) as mock:
            result = self.orch._search_submodule(_sub(), blocks)
        mock.assert_called_once()
        self.assertEqual(result.status, DiffStatus.MODIFIED)
        self.assertEqual(blocks, [])

    def test_url_change_different_repo(self):
        blocks = [_block(url="https://github.com/x/y.git")]
        with patch("yagso.core.orchestrator.GitOperations.is_same_repo",
                   return_value=False):
            result = self.orch._search_submodule(_sub(), blocks)
        self.assertEqual(result.status, DiffStatus.ADDED)
        self.assertEqual(len(blocks), 1)

    def test_added_when_not_found(self):
        blocks = [_block(path="lib2", name="lib2",
                         url="https://github.com/a/c.git")]
        sub = _sub(path="lib3", name="lib3", url="https://github.com/a/d.git")
        result = self.orch._search_submodule(sub, blocks)
        self.assertEqual(result.status, DiffStatus.ADDED)
        self.assertIsNone(result.block)
        self.assertEqual(len(blocks), 1)

    def test_moved_same_identity_different_path(self):
        blocks = [_block(path="old/lib1")]
        result = self.orch._search_submodule(_sub(), blocks)
        self.assertEqual(result.status, DiffStatus.MOVED)
        self.assertEqual(result.name, "lib1")
        self.assertEqual(blocks, [])

    def test_moved_not_poisoned_by_previous_block(self):
        blocks = [_block(path="lib1", name="lib1"),
                  _block(path="lib2", name="lib2")]
        sub = _sub(path="moved/lib1", name="lib1")
        result = self.orch._search_submodule(sub, blocks)
        self.assertEqual(result.status, DiffStatus.MOVED)
        self.assertEqual(result.name, "lib1")
        self.assertEqual([block["name"] for block in blocks], ["lib2"])


class TestPushChanges(unittest.TestCase):

    def test_push_changes_delegates_to_push_all(self):
        orch = SubmoduleOrchestrator(Path("."))
        with patch("yagso.core.orchestrator.GitOperations") as mock_cls:
            mock_ops = mock_cls.return_value.__enter__.return_value
            orch.push_changes()
        mock_ops.push_all.assert_called_once_with()


class TestOrchestratorUrlProtocolChange(BaseGitTest):

    def test_protocol_change_https_to_ssh_detected(self):
        orch = SubmoduleOrchestrator(Path('.'))
        blocks = [{
            "name": "lib1",
            "path": "lib1",
            "url": "git@github.com:Didifred/yagso_test_repo_1.git",
            "commit": "e8e15a1ba0250adaf20ac729e4d3043ac440685d",
        }]

        sub = SubmoduleDefinition(
            root_path="lib1",
            name="lib1",
            path="lib1",
            url="https://github.com/Didifred/yagso_test_repo_1.git",
            commit="e8e15a1ba0250adaf20ac729e4d3043ac440685d",
        )

        searchResult = orch._search_submodule(sub, blocks)
        self.assertEqual(searchResult.status, DiffStatus.MODIFIED)

    def test_protocol_change_ssh_to_https_detected(self):
        orch = SubmoduleOrchestrator(Path('.'))
        blocks = [{
            "name": "lib2",
            "path": "lib2",
            "url": "https://github.com/Didifred/yagso_test_repo_2.git",
            "commit": "3324a351e9b3293ec04e48a7a4003fe853896961",
        }]

        sub = SubmoduleDefinition(
            root_path="lib2",
            name="lib2",
            path="lib2",
            url="git@github.com:Didifred/yagso_test_repo_2.git",
            commit="3324a351e9b3293ec04e48a7a4003fe853896961",
        )

        searchResult = orch._search_submodule(sub, blocks)
        self.assertEqual(searchResult.status, DiffStatus.MODIFIED)


if __name__ == "__main__":
    unittest.main()
