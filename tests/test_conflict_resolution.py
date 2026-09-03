import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from svn_batch_actions.__main__ import validate_action
from svn_batch_actions.actions import ActionExecutor
from svn_batch_actions.utils import svn_merge


class ConflictResolutionValidationTests(unittest.TestCase):
    def test_accepts_svn_conflict_resolution_values_for_regular_merge(self):
        for conflict_resolution in ("mine-conflict", "theirs-conflict"):
            with self.subTest(conflict_resolution=conflict_resolution):
                action = {
                    "from": "trunk",
                    "to": "branches/feature",
                    "rev": "123",
                    "conflict_resolution": conflict_resolution,
                    "msg": "Merge change",
                }

                self.assertEqual([], validate_action(action, 0))

    def test_rejects_invalid_incoming_resolution_configuration(self):
        errors = validate_action(
            {
                "from": "trunk",
                "to": "branches/feature",
                "rev": "123",
                "conflict_resolution": "incoming",
                "msg": "Merge change",
            },
            0,
        )
        self.assertIn(
            "Action 1: 'conflict_resolution' must be one of: mine-conflict, theirs-conflict", errors
        )

        errors = validate_action(
            {
                "to": "branches/feature",
                "patch": True,
                "conflict_resolution": "mine-conflict",
                "msg": "Patch",
            },
            0,
        )
        self.assertIn("Action 1: 'conflict_resolution' is only valid for non-empty merge actions", errors)

        errors = validate_action(
            {
                "from": "trunk",
                "to": "branches/feature",
                "rev": "123",
                "empty": True,
                "conflict_resolution": "theirs-conflict",
                "msg": "Record merge",
            },
            0,
        )
        self.assertIn("Action 1: 'conflict_resolution' is only valid for non-empty merge actions", errors)


class SvnMergeConflictResolutionTests(unittest.TestCase):
    @patch("svn_batch_actions.utils.run_command")
    def test_default_merge_does_not_accept_conflicts(self, run_command):
        run_command.side_effect = [
            subprocess.CompletedProcess([], 0, stdout="U    file.txt\n", stderr=""),
            subprocess.CompletedProcess(
                [],
                0,
                stdout='<?xml version="1.0"?><status><target path="."/></status>',
                stderr="",
            ),
        ]

        success, _output = svn_merge(Path("workspace"), "svn://server/repo/trunk", 123)

        self.assertTrue(success)
        self.assertEqual(
            ["svn", "merge", "-c", "123", "svn://server/repo/trunk"],
            run_command.call_args_list[0].args[0],
        )

    @patch("svn_batch_actions.utils.run_command")
    def test_accepts_theirs_conflict_and_ignores_resolved_summary(self, run_command):
        run_command.side_effect = [
            subprocess.CompletedProcess(
                [],
                0,
                stdout="C    file.txt\nSummary of conflicts:\n  Text conflicts: 0 remaining (and 1 already resolved)\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                [],
                0,
                stdout=(
                    '<?xml version="1.0"?><status><target path="."><entry path="file.txt">'
                    '<wc-status item="modified" props="none" revision="1"/>'
                    "</entry></target></status>"
                ),
                stderr="",
            ),
        ]

        success, output = svn_merge(
            Path("workspace"), "svn://server/repo/trunk", 123, conflict_resolution="theirs-conflict"
        )

        self.assertTrue(success)
        self.assertIn("already resolved", output)
        self.assertEqual(
            ["svn", "merge", "--accept", "theirs-conflict", "-c", "123", "svn://server/repo/trunk"],
            run_command.call_args_list[0].args[0],
        )

    @patch("svn_batch_actions.utils.run_command")
    def test_accepts_mine_conflict(self, run_command):
        run_command.side_effect = [
            subprocess.CompletedProcess([], 0, stdout="C    file.txt\n", stderr=""),
            subprocess.CompletedProcess(
                [],
                0,
                stdout='<?xml version="1.0"?><status><target path="."/></status>',
                stderr="",
            ),
        ]

        success, _output = svn_merge(
            Path("workspace"), "svn://server/repo/trunk", 123, conflict_resolution="mine-conflict"
        )

        self.assertTrue(success)
        self.assertEqual(
            ["svn", "merge", "--accept", "mine-conflict", "-c", "123", "svn://server/repo/trunk"],
            run_command.call_args_list[0].args[0],
        )

    @patch("svn_batch_actions.utils.run_command")
    def test_reports_unresolved_tree_conflict(self, run_command):
        run_command.side_effect = [
            subprocess.CompletedProcess([], 0, stdout="   C directory\n", stderr=""),
            subprocess.CompletedProcess(
                [],
                0,
                stdout=(
                    '<?xml version="1.0"?><status><target path="."><entry path="directory">'
                    '<wc-status item="normal" props="none" revision="1" tree-conflicted="true"/>'
                    "</entry></target></status>"
                ),
                stderr="",
            ),
        ]

        success, output = svn_merge(
            Path("workspace"), "svn://server/repo/trunk", 123, conflict_resolution="theirs-conflict"
        )

        self.assertFalse(success)
        self.assertIn("Unresolved merge conflicts", output)
        self.assertIn("directory", output)


class ActionConflictResolutionTests(unittest.TestCase):
    @patch("svn_batch_actions.actions.cleanup_directory")
    @patch("svn_batch_actions.actions.get_modified_files", return_value=[])
    @patch("svn_batch_actions.actions.svn_merge", return_value=(True, "Merged"))
    @patch("svn_batch_actions.actions.svn_checkout")
    def test_passes_conflict_resolution_to_merge(
        self, _svn_checkout, svn_merge_mock, _get_modified_files, _cleanup_directory
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = MagicMock(verbose=False)
            executor = ActionExecutor("svn://server/repo", Path(temp_dir), logger)

            executor.execute_action(
                0,
                {
                    "from": "trunk",
                    "to": "branches/feature",
                    "rev": "123",
                    "conflict_resolution": "theirs-conflict",
                    "msg": "Merge change",
                },
            )

            svn_merge_mock.assert_called_once_with(
                Path(temp_dir) / "feature",
                "svn://server/repo/trunk",
                123,
                record_only=False,
                conflict_resolution="theirs-conflict",
                verbose=False,
            )


if __name__ == "__main__":
    unittest.main()
