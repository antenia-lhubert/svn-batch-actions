import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from svn_batch_actions.__main__ import validate_action
from svn_batch_actions.patches import AVAILABLE_PATCHES, patch as apply_patches, pom_version


POM = b"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>com.example</groupId>
    <artifactId>parent</artifactId>
    <version>4.0.0</version>
  </parent>
  <artifactId>application</artifactId>
  <version>1.2.3</version>
  <dependencies>
    <dependency>
      <groupId>com.example</groupId>
      <artifactId>library</artifactId>
      <version>7.0.0</version>
    </dependency>
  </dependencies>
</project>
"""


class PomVersionPatchTests(unittest.TestCase):
    def test_updates_only_direct_project_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pom_path = Path(temp_dir) / "pom.xml"
            pom_path.write_bytes(POM)

            pom_version.apply(Path(temp_dir), "2.0.0")

            expected = POM.replace(b"<version>1.2.3</version>", b"<version>2.0.0</version>")
            self.assertEqual(expected, pom_path.read_bytes())

    def test_escapes_xml_characters_in_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pom_path = Path(temp_dir) / "pom.xml"
            pom_path.write_bytes(POM)

            pom_version.apply(Path(temp_dir), "2.0&build")

            self.assertIn(b"<version>2.0&amp;build</version>", pom_path.read_bytes())

    def test_fails_when_project_has_no_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pom_path = Path(temp_dir) / "pom.xml"
            pom_path.write_text("<project><parent><version>1</version></parent></project>", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "direct project <version>"):
                pom_version.apply(Path(temp_dir), "2.0.0")


class PomVersionValidationTests(unittest.TestCase):
    def test_accepts_pom_version_patch_config(self):
        action = {
            "to": "branches/feature",
            "patch": True,
            "enabled_patches": ["pom_version"],
            "pom_version": "2.0.0",
            "msg": "Update version",
        }

        self.assertEqual([], validate_action(action, 0))

    def test_requires_pom_version_when_patch_is_enabled(self):
        action = {
            "to": "branches/feature",
            "patch": True,
            "enabled_patches": ["pom_version"],
            "msg": "Update version",
        }

        self.assertIn("Action 1: Patch 'pom_version' requires field 'pom_version'", validate_action(action, 0))


class ConfigurablePatchDispatchTests(unittest.TestCase):
    def test_default_selection_includes_configurable_patch_only_when_configured(self):
        regular_patch = SimpleNamespace(apply=MagicMock())
        configured_patch = SimpleNamespace(CONFIG_KEY="pom_version", apply=MagicMock())

        with patch.dict(
            AVAILABLE_PATCHES,
            {"regular": regular_patch, "pom_version": configured_patch},
            clear=True,
        ):
            apply_patches(Path("."), action_config={})
            configured_patch.apply.assert_not_called()

            apply_patches(Path("."), action_config={"pom_version": "2.0.0"})
            configured_patch.apply.assert_called_once_with(Path("."), "2.0.0", False)


if __name__ == "__main__":
    unittest.main()
