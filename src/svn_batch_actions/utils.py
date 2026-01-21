"""Utility functions for SVN operations."""

import shutil
import subprocess
import sys
from pathlib import Path
from time import sleep
from typing import Optional


class SVNCommandError(Exception):
    """Exception raised when an SVN command fails."""
    pass


def run_command(
    command: list[str],
    cwd: Optional[Path] = None,
    check: bool = True,
    capture_output: bool = True
) -> subprocess.CompletedProcess:
    """Execute a shell command and return the result."""
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            check=check,
        )
        return result
    except subprocess.CalledProcessError as e:
        error_msg = f"Command failed: {' '.join(command)}\n"
        error_msg += f"Exit code: {e.returncode}\n"
        if e.stdout:
            error_msg += f"stdout: {e.stdout}\n"
        if e.stderr:
            error_msg += f"stderr: {e.stderr}"
        raise SVNCommandError(error_msg) from e


def cleanup_directory(directory: Path, verbose: bool = False) -> None:
    """Forcefully cleanup a directory, handling Windows file locks."""
    if not directory.exists():
        return

    if verbose:
        print(f"Cleaning up directory: {directory}")

    try:
        # First try normal removal
        shutil.rmtree(directory, ignore_errors=False)
    except Exception:
        # On Windows, try harder with file attribute changes
        import stat
        import os

        def handle_remove_readonly(func, path, exc):
            """Error handler for Windows readonly files."""
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass

        shutil.rmtree(directory, onerror=handle_remove_readonly)


def svn_checkout(url: str, target_dir: Path, verbose: bool = False, depth: Optional[str] = None) -> None:
    """
    Checkout an SVN branch.

    Args:
        url: SVN URL to checkout
        target_dir: Local directory path
        verbose: Enable verbose output
        depth: Checkout depth (empty, files, immediates, infinity). None uses default (infinity).
    """
    if verbose:
        depth_msg = f" with --depth {depth}" if depth else ""
        print(f"Checking out: {url}{depth_msg}")

    cmd = ["svn", "checkout"]
    if depth:
        cmd.extend(["--depth", depth])
    cmd.extend([url, str(target_dir)])

    run_command(cmd)


def svn_merge(
    working_dir: Path,
    source_url: str,
    revision: int,
    record_only: bool = False,
    verbose: bool = False
) -> tuple[bool, str]:
    """
    Perform SVN merge.

    Returns:
        (success, output_message)
    """
    merge_cmd = ["svn", "merge"]

    if record_only:
        merge_cmd.append("--record-only")

    merge_cmd.extend(["-c", str(revision), source_url])

    if verbose:
        print(f"Running merge: {' '.join(merge_cmd)}")

    result = run_command(merge_cmd, cwd=working_dir, check=False)

    # Check for conflicts
    if record_only:
        # For record-only merges, only check for actual conflicts (marked with 'C')
        # Skipped paths are expected with sparse checkouts and are not failures
        output_combined = f"{result.stdout}\n{result.stderr}"
        if any(line.strip().startswith('C ') for line in output_combined.splitlines()):
            return False, f"Merge conflicts detected:\n{result.stdout}\n{result.stderr}"
    else:
        # For regular merges, any mention of conflict is a problem
        if "conflict" in result.stdout.lower() or "conflict" in result.stderr.lower():
            return False, f"Merge conflicts detected:\n{result.stdout}\n{result.stderr}"

    if result.returncode != 0:
        # Check if already merged
        if "already reflects" in result.stderr or "already been merged" in result.stderr:
            return True, "Revision already merged"
        return False, f"Merge failed:\n{result.stdout}\n{result.stderr}"

    return True, result.stdout


def svn_commit(
    working_dir: Path,
    message: str,
    author: Optional[str] = None,
    verbose: bool = False
) -> tuple[bool, str]:
    """
    Commit changes to SVN.

    Returns:
        (has_changes, output_message)
    """
    # Check if there are changes
    status_result = run_command(["svn", "status"], cwd=working_dir, check=False)

    if not status_result.stdout.strip():
        return False, "No changes to commit"

    if verbose:
        print("SVN status:")
        print(status_result.stdout)

    # Add all modified and new files
    run_command(["svn", "add", "--force", "."], cwd=working_dir, check=False)

    # Build commit command
    commit_cmd = ["svn", "commit", "-m", message]

    if author:
        commit_cmd.extend(["--username", author])

    result = run_command(commit_cmd, cwd=working_dir)

    return True, result.stdout


def svn_revert_all(working_dir: Path, verbose: bool = False) -> None:
    """Revert all changes in working directory."""
    if verbose:
        print("Reverting all changes")
    run_command(["svn", "revert", "-R", "."], cwd=working_dir, check=False)


def get_modified_files(working_dir: Path) -> list[str]:
    """Get list of modified files from SVN status."""
    result = run_command(["svn", "status"], cwd=working_dir, check=False)

    modified_files = []
    for line in result.stdout.splitlines():
        if line.strip():
            # Parse SVN status format: "M      path/to/file.txt"
            parts = line.split(None, 1)
            if len(parts) == 2:
                modified_files.append(parts[1])

    return modified_files


def fix_mergeinfo_inheritance(working_dir: Path, revision: int, verbose: bool = False) -> bool:
    """
    Remove non-inheritable marker (*) from a specific revision in svn:mergeinfo property.

    This converts a non-inheritable merge (created with sparse checkout)
    into an inheritable merge for the specified revision only.

    Args:
        working_dir: Working directory path
        revision: The revision number to fix (remove asterisk from)
        verbose: Enable verbose output

    Returns:
        True if mergeinfo was modified, False if no changes needed
    """
    if verbose:
        print(f"Checking svn:mergeinfo for non-inheritable marker on r{revision}")

    # Get current mergeinfo as bytes to preserve exact encoding
    result = subprocess.run(
        ["svn", "propget", "svn:mergeinfo", "."],
        cwd=working_dir,
        capture_output=True,
        check=False
    )

    if result.returncode != 0 or not result.stdout.strip():
        # No mergeinfo property exists
        if verbose:
            print("No svn:mergeinfo property found")
        return False

    original_mergeinfo_bytes = result.stdout.rstrip(b'\r\n')

    # Remove asterisk only from the specific revision (work with bytes to preserve encoding)
    # Pattern: b"195472*" -> b"195472" (but leave other asterisks intact)
    search_pattern = f'{revision}*'.encode('ascii')
    replace_pattern = f'{revision}'.encode('ascii')
    fixed_mergeinfo_bytes = original_mergeinfo_bytes.replace(search_pattern, replace_pattern)

    if original_mergeinfo_bytes == fixed_mergeinfo_bytes:
        if verbose:
            print(f"No non-inheritable marker found for r{revision}")
        return False

    if verbose:
        # Try to decode for display, but don't fail if we can't
        try:
            original_display = original_mergeinfo_bytes.decode('utf-8', errors='replace')
            fixed_display = fixed_mergeinfo_bytes.decode('utf-8', errors='replace')
            print(f"Original mergeinfo:\n{original_display}")
            print(f"Fixed mergeinfo:\n{fixed_display}")
        except Exception:
            print(f"Original mergeinfo (bytes): {original_mergeinfo_bytes[:200]}...")
            print(f"Fixed mergeinfo (bytes): {fixed_mergeinfo_bytes[:200]}...")

    # Set the corrected mergeinfo using a temp file to avoid Windows command line length limits
    import tempfile

    temp_file = None
    try:
        # Write mergeinfo as binary to preserve exact encoding
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as f:
            f.write(fixed_mergeinfo_bytes)
            temp_file = f.name

        # Set property from file
        subprocess.run(
            ["svn", "propset", "svn:mergeinfo", "--file", temp_file, "."],
            cwd=working_dir,
            capture_output=True,
            check=True
        )
    finally:
        # Clean up temp file
        if temp_file and Path(temp_file).exists():
            Path(temp_file).unlink()

    if verbose:
        print(f"Successfully removed non-inheritable marker from r{revision}")

    return True
