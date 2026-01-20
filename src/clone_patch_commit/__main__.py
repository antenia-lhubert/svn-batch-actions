import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# List of SVN branches to process
SVN_BRANCHES = [
    # "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_camcalux",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_2a",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_aesio",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_airbus",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_bpce",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_camca",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_cfdp",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_cocoon",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_collecteam",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_covea",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_demo_iard",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_edf",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_enccas",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_faa",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_generation",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_gli",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_ipbp",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_lmg",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_madp",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_matmut",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_mudetaf",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_mutex",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_mutualisee",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_praga",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_saam",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_swisslife",
    "svn://leader-svn.leaderinfo.com/novanet/versions/version-1.5_validee",
]

# Predefined commit message
COMMIT_MESSAGE = """[BUG] - Mantis : 65813 : Résolution des problèmes d'encodage dans NEO Core

> Surcharge du charset réponse des JSP en UTF-8
> Configurations"""


def run_command(command: list[str], cwd: Path = None, check: bool = True) -> subprocess.CompletedProcess:
    """Execute a shell command and return the result."""
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=check,
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(command)}", file=sys.stderr)
        print(f"Exit code: {e.returncode}", file=sys.stderr)
        print(f"stdout: {e.stdout}", file=sys.stderr)
        print(f"stderr: {e.stderr}", file=sys.stderr)
        raise


def clone_branch(branch_url: str, target_dir: Path, verbose: bool = False) -> bool:
    """Clone an SVN branch to the target directory."""
    if verbose:
        print(f"\nCloning branch: {branch_url}")
        print(f"Target directory: {target_dir}")

    try:
        result = run_command(["svn", "checkout", branch_url, str(target_dir)])
        if verbose:
            print(f"Clone successful: {branch_url}")
        return True
    except subprocess.CalledProcessError:
        print(f"Failed to clone branch: {branch_url}", file=sys.stderr)
        return False


def apply_patches(working_dir: Path, verbose: bool = False) -> bool:
    """Apply UTF-8 patches using the jsp_to_utf8_headers module."""
    if verbose:
        print(f"\nApplying patches to: {working_dir}")

    try:
        # Import the patching logic
        from jsp_to_utf8_headers.__main__ import process_files, apply_targeted_replacements, IGNORE_PATTERNS

        # Find all JSP files in the working directory
        jsp_files = list(working_dir.rglob("*.jsp"))

        # Filter out ignored patterns
        files_to_process = [
            p for p in jsp_files
            if not any(p.match(pattern) for pattern in IGNORE_PATTERNS)
        ]

        if verbose:
            print(f"Found {len(jsp_files)} JSP files, processing {len(files_to_process)}")

        # Process JSP files
        process_files(files_to_process, verbose)

        # Apply targeted replacements
        apply_targeted_replacements(working_dir, verbose)

        if verbose:
            print("Patches applied successfully")

        return True
    except Exception as e:
        print(f"Failed to apply patches: {e}", file=sys.stderr)
        return False


def commit_changes(working_dir: Path, commit_message: str, verbose: bool = False) -> bool:
    """Commit changes to the SVN repository."""
    if verbose:
        print(f"\nCommitting changes with message: {commit_message}")

    try:
        # Check SVN status to see if there are changes
        status_result = run_command(["svn", "status"], cwd=working_dir, check=False)

        if not status_result.stdout.strip():
            print("No changes to commit")
            return True

        if verbose:
            print("SVN status:")
            print(status_result.stdout)

        # Add all modified and new files
        run_command(["svn", "add", "--force", "."], cwd=working_dir, check=False)

        # Commit the changes
        result = run_command(["svn", "commit", "-m", commit_message], cwd=working_dir)

        if verbose:
            print("Commit successful")
            print(result.stdout)

        return True
    except subprocess.CalledProcessError:
        print(f"Failed to commit changes in: {working_dir}", file=sys.stderr)
        return False


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
        def handle_remove_readonly(func, path, exc):
            """Error handler for Windows readonly files."""
            try:
                import os
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass

        shutil.rmtree(directory, onerror=handle_remove_readonly)


def process_branch(branch_url: str, workspace_dir: Path, verbose: bool = False, keep_workspace: bool = False) -> None:
    """Process a single branch: clone, patch, and commit. Raises exception on error."""
    # Extract branch name from URL
    branch_name = branch_url.rstrip('/').split('/')[-1]
    working_dir = workspace_dir / branch_name

    print(f"\n{'=' * 60}")
    print(f"Processing branch: {branch_name}")
    print(f"{'=' * 60}")

    # Clean up any existing working directory before starting
    cleanup_directory(working_dir, verbose)

    try:
        # Step 1: Clone
        if not clone_branch(branch_url, working_dir, verbose):
            raise RuntimeError(f"Failed to clone branch: {branch_url}")

        # Step 2: Apply patches
        if not apply_patches(working_dir, verbose):
            raise RuntimeError(f"Failed to apply patches to: {branch_name}")

        # Step 3: Commit changes
        if not commit_changes(working_dir, COMMIT_MESSAGE, verbose):
            raise RuntimeError(f"Failed to commit changes to: {branch_name}")

        print(f"✓ Successfully processed branch: {branch_name}")

    finally:
        # Clean up working directory unless keep_workspace is True
        if not keep_workspace:
            cleanup_directory(working_dir, verbose)


def main():
    parser = argparse.ArgumentParser(
        description="Clone SVN branches, apply patches, and commit changes."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed progress information.",
    )
    parser.add_argument(
        "-k",
        "--keep-workspace",
        action="store_true",
        help="Keep cloned workspace directories after processing.",
    )
    parser.add_argument(
        "-w",
        "--workspace",
        type=str,
        default="./.temp",
        help="Workspace directory for cloning branches (default: ./.temp).",
    )
    parser.add_argument(
        "--branches",
        type=str,
        nargs="+",
        help="Specific branch URLs to process (overrides default branch list).",
    )
    parser.add_argument(
        "--commit-message",
        type=str,
        help="Custom commit message (overrides default).",
    )

    args = parser.parse_args()

    # Use custom branches if provided, otherwise use default list
    branches_to_process = args.branches if args.branches else SVN_BRANCHES
    commit_msg = args.commit_message if args.commit_message else COMMIT_MESSAGE

    # Create workspace directory
    workspace_dir = Path(args.workspace).resolve()
    workspace_dir.mkdir(parents=True, exist_ok=True)

    if args.verbose:
        print(f"Workspace directory: {workspace_dir}")
        print(f"Branches to process: {len(branches_to_process)}")
        print(f"Commit message: {commit_msg}")

    # Process each branch - will stop on first error
    try:
        for i, branch_url in enumerate(branches_to_process, 1):
            print(f"\nProcessing branch {i}/{len(branches_to_process)}")
            process_branch(
                branch_url,
                workspace_dir,
                verbose=args.verbose,
                keep_workspace=args.keep_workspace
            )

        # All branches processed successfully
        print(f"\n{'=' * 60}")
        print("SUCCESS")
        print(f"{'=' * 60}")
        print(f"✓ All {len(branches_to_process)} branches processed successfully!")
        sys.exit(0)

    except Exception as e:
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("ERROR", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"✗ Processing stopped due to error:", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)

        if args.verbose:
            import traceback
            print(f"\nFull traceback:", file=sys.stderr)
            traceback.print_exc()

        sys.exit(1)


if __name__ == "__main__":
    main()
