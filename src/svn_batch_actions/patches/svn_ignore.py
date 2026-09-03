"""Patch the root directory's svn:ignore property."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ..utils import run_command, SVNCommandError


CONFIG_KEY = "svn_ignore"


def apply(working_dir: Path, ignore_entry: str, verbose: bool = False) -> None:
    """Add one line to svn:ignore while preserving existing entries."""
    result = run_command(["svn", "proplist", "--xml", "--verbose", "."], cwd=working_dir, check=False)
    if result.returncode != 0:
        raise SVNCommandError(f"Unable to read svn:ignore property:\n{result.stderr}")

    try:
        properties = ET.fromstring(result.stdout)
    except ET.ParseError as error:
        raise SVNCommandError(f"Unable to parse SVN properties while reading svn:ignore: {error}") from error

    ignore_property = properties.find(".//property[@name='svn:ignore']")
    current_value = (ignore_property.text or "") if ignore_property is not None else ""
    if ignore_entry in current_value.splitlines():
        if verbose:
            print(f"svn:ignore already contains: {ignore_entry}")
        return

    existing_line_ending = re.search(r"\r\n|\r|\n", current_value)
    line_ending = existing_line_ending.group(0) if existing_line_ending else "\n"
    separator = "" if not current_value or current_value.endswith(("\r", "\n")) else line_ending
    new_value = f"{current_value}{separator}{ignore_entry}{line_ending}"
    run_command(["svn", "propset", "svn:ignore", new_value, "."], cwd=working_dir)

    if verbose:
        print(f"Added to svn:ignore: {ignore_entry}")
