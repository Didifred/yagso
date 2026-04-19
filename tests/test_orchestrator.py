import unittest
from pathlib import Path

from yagso.core.orchestrator import SubmoduleOrchestrator, DiffStatus
from yagso.domain.submodule import SubmoduleDefinition


class TestOrchestratorUrlProtocolChange(unittest.TestCase):
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

        status = orch._search_submodule(sub, blocks)
        self.assertEqual(status, DiffStatus.MODIFIED)

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

        status = orch._search_submodule(sub, blocks)
        self.assertEqual(status, DiffStatus.MODIFIED)


if __name__ == "__main__":
    unittest.main()
