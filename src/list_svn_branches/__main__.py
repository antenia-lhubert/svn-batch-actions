import subprocess
import sys
import argparse
import re
from typing import List


def run_svn_list(repository_url: str, verbose: bool = False) -> str:
    """Execute svn list command and return the output."""
    if verbose:
        print(f"Listing branches from: {repository_url}")

    try:
        result = subprocess.run(
            ["svn", "list", repository_url],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error executing svn list: {e}", file=sys.stderr)
        print(f"stderr: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def filter_branches(branches: List[str], pattern: str, verbose: bool = False) -> List[str]:
    """Filter branches based on a regex pattern."""
    if not pattern:
        return branches

    if verbose:
        print(f"Filtering branches with pattern: {pattern}")

    try:
        regex = re.compile(pattern)
        filtered = [branch for branch in branches if regex.search(branch)]
        return filtered
    except re.error as e:
        print(f"Invalid regex pattern '{pattern}': {e}", file=sys.stderr)
        sys.exit(1)


def list_branches(repository_url: str, pattern: str = None, verbose: bool = False, full_url: bool = False) -> List[str]:
    """List all branches from an SVN repository, optionally filtering by pattern."""
    # Get the raw output from svn list
    output = run_svn_list(repository_url, verbose)

    # Parse branch names (remove trailing slashes and empty lines)
    branches = [line.rstrip('/') for line in output.splitlines() if line.strip()]

    if verbose:
        print(f"Found {len(branches)} branches total")

    # Filter by pattern if provided
    if pattern:
        branches = filter_branches(branches, pattern, verbose)
        if verbose:
            print(f"Filtered to {len(branches)} branches matching pattern")

    # Optionally return full URLs
    if full_url:
        base_url = repository_url.rstrip('/')
        branches = [f"{base_url}/{branch}" for branch in branches]

    return branches


def main():
    parser = argparse.ArgumentParser(
        description="List SVN branches from a repository with optional pattern filtering."
    )
    parser.add_argument(
        "repository_url",
        type=str,
        help="URL to the SVN branches directory (e.g., https://svn.example.com/repo/branches)",
    )
    parser.add_argument(
        "-p",
        "--pattern",
        type=str,
        help="Regex pattern to filter branch names (e.g., 'release.*' or 'feature/.*')",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed information.",
    )
    parser.add_argument(
        "-f",
        "--full-url",
        action="store_true",
        help="Output full URLs instead of just branch names.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Write output to a file instead of stdout.",
    )
    parser.add_argument(
        "-c",
        "--count",
        action="store_true",
        help="Only display the count of matching branches.",
    )

    args = parser.parse_args()

    # List and filter branches
    branches = list_branches(
        args.repository_url,
        pattern=args.pattern,
        verbose=args.verbose,
        full_url=args.full_url
    )

    # Handle count-only mode
    if args.count:
        print(len(branches))
        return

    # Format output
    if not branches:
        print("No branches found matching the criteria.")
        return

    output_text = "\n".join(branches)

    # Write to file or stdout
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_text + "\n")
            if args.verbose:
                print(f"Output written to: {args.output}")
                print(f"Total branches: {len(branches)}")
        except IOError as e:
            print(f"Error writing to file {args.output}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(output_text)
        if args.verbose:
            print(f"\nTotal branches: {len(branches)}")


if __name__ == "__main__":
    main()
