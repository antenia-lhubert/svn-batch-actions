import io
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from svn_batch_actions.__main__ import main
from svn_batch_actions.actions import ActionExecutor
from svn_batch_actions.utils import SVNCommandError


ACTIONS = [
    {"to": "branches/feature", "patch": True, "msg": "Patch"},
    {"from": "trunk", "to": "branches/feature", "rev": "123", "empty": True, "msg": "Record merge"},
    {"from": "trunk", "to": "branches/feature", "rev": "123", "msg": "Merge"},
    {"from": "trunk", "to": "branches/feature", "rev": "123", "patch": True, "msg": "Merge and patch"},
]


class NoCleanupTests(unittest.TestCase):
    def run_action(self, action, outcome="success", **options):
        with ExitStack() as stack:
            temp_dir = stack.enter_context(tempfile.TemporaryDirectory())
            working_dir = Path(temp_dir) / "feature"
            working_dir.mkdir()
            project_file = working_dir / "project.txt"
            project_file.write_text("Keep my project", encoding="utf-8")

            # Use real directory cleanup, but isolate all SVN operations.
            checkout = stack.enter_context(patch("svn_batch_actions.actions.svn_checkout"))
            merge = stack.enter_context(patch("svn_batch_actions.actions.svn_merge", return_value=(True, "Merged")))
            commit = stack.enter_context(
                patch("svn_batch_actions.actions.svn_commit", return_value=(True, "Committed revision 124."))
            )
            revert = stack.enter_context(patch("svn_batch_actions.actions.svn_revert_all"))
            stack.enter_context(patch("svn_batch_actions.actions.fix_mergeinfo_inheritance"))
            stack.enter_context(
                patch(
                    "svn_batch_actions.actions.get_modified_files",
                    return_value=[] if outcome == "no_changes" else ["project.txt"],
                )
            )
            executor = ActionExecutor("svn://server/repo", Path(temp_dir), MagicMock(verbose=False), **options)
            executor._apply_patches = MagicMock()

            if outcome == "checkout_error":
                checkout.side_effect = SVNCommandError("Checkout failed")
            elif outcome == "commit_error":
                commit.side_effect = SVNCommandError("Commit failed")
            elif outcome == "patch_error":
                executor._apply_patches.side_effect = RuntimeError("Patch failed")
            elif outcome == "merge_error":
                merge.return_value = (False, "Conflict")

            if outcome.endswith("_error"):
                with self.assertRaises(SVNCommandError):
                    executor.execute_action(0, action)
            else:
                self.assertTrue(executor.execute_action(0, action))

            preserved = options.get("no_cleanup") or options.get("dry_run") or options.get("no_commit")
            self.assertEqual(bool(preserved), working_dir.exists())
            if options.get("no_cleanup") or options.get("dry_run"):
                self.assertEqual("Keep my project", project_file.read_text(encoding="utf-8"))
            if outcome == "success" and not options.get("dry_run") and not options.get("no_commit"):
                commit.assert_called_once()
            elif outcome != "commit_error":
                commit.assert_not_called()
            if options.get("apply_only") or options.get("dry_run"):
                checkout.assert_not_called()
            else:
                checkout.assert_called_once()
            if outcome == "merge_error" and not action.get("empty"):
                revert.assert_called_once()

    def test_preserves_all_action_types_on_success_no_changes_and_errors(self):
        for action in ACTIONS:
            outcomes = ["success", "no_changes", "checkout_error", "commit_error"]
            if "from" in action:
                outcomes.append("merge_error")
            if action.get("patch"):
                outcomes.append("patch_error")
            for outcome in outcomes:
                with self.subTest(action=action, outcome=outcome):
                    self.run_action(action, outcome, no_cleanup=True)

    def test_apply_only_preserves_existing_project(self):
        for outcome in ["success", "no_changes", "patch_error", "commit_error"]:
            with self.subTest(outcome=outcome):
                self.run_action(ACTIONS[0], outcome, no_cleanup=True, apply_only=True)

    def test_dry_run_preserves_existing_project_for_all_action_types(self):
        for action in ACTIONS:
            with self.subTest(action=action):
                self.run_action(action, dry_run=True)

    def test_default_cleanup_still_removes_workspace_on_success_and_error(self):
        for action in ACTIONS:
            for outcome in ["success", "commit_error"]:
                with self.subTest(action=action, outcome=outcome):
                    self.run_action(action, outcome)

    def test_no_commit_combines_with_no_cleanup(self):
        self.run_action(ACTIONS[0], no_cleanup=True, no_commit=True)

    @patch("svn_batch_actions.__main__.ActionExecutor")
    @patch("svn_batch_actions.__main__.ActionLogger")
    @patch("svn_batch_actions.__main__.load_config", return_value={"repository_base": "url", "actions": [ACTIONS[0]]})
    def test_cli_passes_no_cleanup_to_executor(self, _load_config, _logger, executor):
        for flags, expected in [([], False), (["--no-cleanup"], True)]:
            with self.subTest(flags=flags):
                with patch("sys.argv", ["svn-batch", "config.json", "-y", *flags]), redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as result:
                        main()
                self.assertEqual(0, result.exception.code)
                self.assertEqual(expected, executor.call_args.kwargs["no_cleanup"])


if __name__ == "__main__":
    unittest.main()
