import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from svn_batch_actions.__main__ import validate_action, validate_config
from svn_batch_actions.actions import ActionExecutor
from svn_batch_actions.logger import ActionLogger


class CheckoutDepthTests(unittest.TestCase):
    def test_checkout_depth_validation(self):
        config = {
            "repository_base": "url",
            "checkout_depth": "files",
            "actions": [{"to": "branches/feature", "patch": True, "msg": "Patch"}],
        }
        self.assertEqual([], validate_config(config))

        errors = validate_action(
            {"to": "branches/feature", "patch": True, "msg": "Patch", "checkout_depth": "children"}, 0
        )
        self.assertIn("Action 1: 'checkout_depth' must be one of: empty, files, immediates, infinity", errors)

    @patch("svn_batch_actions.actions.cleanup_directory")
    @patch("svn_batch_actions.actions.get_modified_files", return_value=[])
    @patch("svn_batch_actions.actions.svn_checkout")
    def test_action_depth_overrides_default(self, svn_checkout, _get_modified_files, _cleanup_directory):
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = MagicMock(verbose=False)
            executor = ActionExecutor("svn://server/repo", Path(temp_dir), logger, checkout_depth="infinity")
            executor._apply_patches = MagicMock()

            executor.execute_action(
                0,
                {
                    "to": "branches/feature",
                    "patch": True,
                    "checkout_depth": "files",
                    "msg": "Patch root files",
                },
            )

            svn_checkout.assert_called_once_with(
                "svn://server/repo/branches/feature",
                Path(temp_dir) / "feature",
                False,
                depth="files",
            )


class CommitOutputTests(unittest.TestCase):
    @patch("builtins.print")
    def test_commit_result_is_printed_without_verbose_logging(self, print_mock):
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = ActionLogger(Path(temp_dir), verbose=False)
            logger.log_step("Commit result", "Committed revision 12345.", always_print=True)

            printed_output = "".join(call.args[0] for call in print_mock.call_args_list)
            self.assertIn("Committed revision 12345.", printed_output)


if __name__ == "__main__":
    unittest.main()
