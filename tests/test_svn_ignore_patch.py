import subprocess
import unittest
from pathlib import Path
from unittest.mock import call, patch

from svn_batch_actions.__main__ import validate_action
from svn_batch_actions.actions import ActionExecutor
from svn_batch_actions.logger import ActionLogger
from svn_batch_actions.patches import AVAILABLE_PATCHES, patch as apply_patches, svn_ignore


class SvnIgnoreValidationTests(unittest.TestCase):
    def test_accepts_svn_ignore_patch(self):
        action = {
            "to": "branches/feature",
            "patch": True,
            "enabled_patches": ["svn_ignore"],
            "svn_ignore": "target",
            "msg": "Ignore target",
        }

        self.assertEqual([], validate_action(action, 0))
        self.assertEqual("PATCH", ActionExecutor._infer_action_type(action))
        self.assertEqual("PATCH", ActionLogger._infer_action_type(action))
        self.assertIn("svn_ignore", AVAILABLE_PATCHES)

    def test_defaults_to_svn_ignore_patch_when_configured(self):
        with patch.dict(AVAILABLE_PATCHES, {"svn_ignore": svn_ignore}, clear=True), patch.object(
            svn_ignore, "apply"
        ) as apply_mock:
            apply_patches(Path("workspace"), action_config={"svn_ignore": "target"})

        apply_mock.assert_called_once_with(Path("workspace"), "target", False)

    def test_rejects_empty_and_multiline_values(self):
        empty_errors = validate_action(
            {"to": "branches/feature", "patch": True, "svn_ignore": " ", "msg": "Ignore target"}, 0
        )
        self.assertIn("Action 1: 'svn_ignore' must be a non-empty string", empty_errors)

        multiline_errors = validate_action(
            {
                "to": "branches/feature",
                "patch": True,
                "svn_ignore": "target\nbuild",
                "msg": "Ignore output",
            },
            0,
        )
        self.assertIn("Action 1: 'svn_ignore' must contain exactly one line", multiline_errors)

    def test_requires_patch_flag_and_configuration(self):
        no_patch_errors = validate_action(
            {"to": "branches/feature", "svn_ignore": "target", "msg": "Ignore target"}, 0
        )
        self.assertIn("Action 1: 'svn_ignore' requires 'patch': true", no_patch_errors)

        missing_config_errors = validate_action(
            {
                "to": "branches/feature",
                "patch": True,
                "enabled_patches": ["svn_ignore"],
                "msg": "Ignore target",
            },
            0,
        )
        self.assertIn("Action 1: Patch 'svn_ignore' requires field 'svn_ignore'", missing_config_errors)


class SvnIgnorePatchTests(unittest.TestCase):
    @patch("svn_batch_actions.patches.svn_ignore.run_command")
    def test_appends_entry_to_existing_property(self, run_command):
        run_command.side_effect = [
            subprocess.CompletedProcess(
                [],
                0,
                stdout=(
                    '<?xml version="1.0"?><properties><target path=".">'
                    '<property name="svn:ignore">build\n*.tmp\n</property>'
                    "</target></properties>"
                ),
                stderr="",
            ),
            subprocess.CompletedProcess([], 0, stdout="property set", stderr=""),
        ]

        svn_ignore.apply(Path("workspace"), "target")

        self.assertEqual(
            call(["svn", "propset", "svn:ignore", "build\n*.tmp\ntarget\n", "."], cwd=Path("workspace")),
            run_command.call_args_list[1],
        )

    @patch("svn_batch_actions.patches.svn_ignore.run_command")
    def test_does_not_add_duplicate_entry(self, run_command):
        run_command.return_value = subprocess.CompletedProcess(
            [],
            0,
            stdout=(
                '<?xml version="1.0"?><properties><target path=".">'
                '<property name="svn:ignore">build\ntarget\n</property>'
                "</target></properties>"
            ),
            stderr="",
        )

        svn_ignore.apply(Path("workspace"), "target")

        run_command.assert_called_once_with(
            ["svn", "proplist", "--xml", "--verbose", "."], cwd=Path("workspace"), check=False
        )

    @patch("svn_batch_actions.patches.svn_ignore.run_command")
    def test_preserves_existing_crlf_line_endings(self, run_command):
        run_command.side_effect = [
            subprocess.CompletedProcess(
                [],
                0,
                stdout=(
                    '<?xml version="1.0"?><properties><target path=".">'
                    '<property name="svn:ignore">.settings&#13;\n.classpath&#13;\ntarget&#13;\n</property>'
                    "</target></properties>"
                ),
                stderr="",
            ),
            subprocess.CompletedProcess([], 0, stdout="property set", stderr=""),
        ]

        svn_ignore.apply(Path("workspace"), ".local")

        self.assertEqual(
            call(
                [
                    "svn",
                    "propset",
                    "svn:ignore",
                    ".settings\r\n.classpath\r\ntarget\r\n.local\r\n",
                    ".",
                ],
                cwd=Path("workspace"),
            ),
            run_command.call_args_list[1],
        )

    @patch("svn_batch_actions.patches.svn_ignore.run_command")
    def test_creates_property_when_missing(self, run_command):
        run_command.side_effect = [
            subprocess.CompletedProcess(
                [],
                0,
                stdout='<?xml version="1.0"?><properties><target path="."/></properties>',
                stderr="",
            ),
            subprocess.CompletedProcess([], 0, stdout="property set", stderr=""),
        ]

        svn_ignore.apply(Path("workspace"), "target")

        self.assertEqual(
            call(["svn", "propset", "svn:ignore", "target\n", "."], cwd=Path("workspace")),
            run_command.call_args_list[1],
        )
if __name__ == "__main__":
    unittest.main()
