import argparse
import re
import sys
from pathlib import Path

NEW_PAGE_CONTENT_TYPE_DIRECTIVE = (
    '<%@page contentType="text/html;charset=UTF-8"%>'
)

EXISTING_PAGE_CONTENT_TYPE_REGEX = re.compile(
    r"<\s*%\s*@\s*page[^%]*contentType\s?=[^%]*%\s*>", re.IGNORECASE
)

REMOVAL_PAGE_DIRECTIVE_REGEX = re.compile(
    r'[ \t\f]*<%\s*@\s*page[^%]*contentType\s?=(?:(?!xml)[^%])*%>\s*[\r\n]*',
    re.IGNORECASE,
)

REMOVAL_META_HTTP_EQUIV_REGEX = re.compile(
    r'[ \t\f]*<meta[^>]*http-equiv=["\']?Content-Type[^>]*>[\r\n]*',
    re.IGNORECASE,
)

REMOVAL_META_CHARSET_REGEX = re.compile(
    r'[ \t\f]*<meta[^>]*charset=["\']?[^>]*>[\r\n]*', re.IGNORECASE
)

REMOVAL_FORM_ACCEPT_CHARSET_REGEX = re.compile(
    r'(<form[^>]+)\s*(?:accept-charset|acceptCharset)\s?=\s?["\'][^"\']+["\']',
    re.IGNORECASE,
)

IGNORE_PATTERNS = [
    "**/target/**/*",
    "**/.svn/**/*   ",
    "**/.idea/**/*",
    "**/.git/**/*",
    "**/node_modules/**/*",
]


def process_files(files_to_process: list[Path], verbose: bool):
    if not files_to_process:
        print("No valid JSP files or directories found to process.")
        return

    modified_files = set()

    print(
        "Removing existing contentType directives and meta tags from JSP files..."
    )

    for file_path in files_to_process:
        try:
            original_content = file_path.read_text(encoding="latin1")
            content = original_content

            content = REMOVAL_PAGE_DIRECTIVE_REGEX.sub("", content)
            content = REMOVAL_META_HTTP_EQUIV_REGEX.sub("", content)
            content = REMOVAL_META_CHARSET_REGEX.sub("", content)
            content = REMOVAL_FORM_ACCEPT_CHARSET_REGEX.sub(r"\1", content)

            if not EXISTING_PAGE_CONTENT_TYPE_REGEX.search(content):
                content = NEW_PAGE_CONTENT_TYPE_DIRECTIVE + "\n" + content

            if content != original_content:
                if verbose:
                    print(f"Modified: {file_path}")
                modified_files.add(file_path)
                file_path.write_text(content, encoding="latin1")

        except (IOError, UnicodeDecodeError) as e:
            print(f"Error processing file {file_path}: {e}", file=sys.stderr)

    print("\n--- Summary of Changes ---")
    if modified_files:
        print(f"Total files modified: {len(modified_files)}")
        if not verbose:
            print("Run with -v or --verbose for details on each file.")
    else:
        print("No files were modified.")


def main():
    parser = argparse.ArgumentParser(
        description="Process JSP files to standardize page contentType directives."
    )
    parser.add_argument(
        "paths",
        metavar="path",
        type=str,
        nargs="+",
        help="One or more paths to process (files or directories).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print more details about changes.",
    )
    args = parser.parse_args()

    files_to_process = []
    for input_path_str in args.paths:
        input_path = Path(input_path_str).resolve()
        if not input_path.exists():
            print(
                f"Warning: Path does not exist, skipping: {input_path}",
                file=sys.stderr,
            )
            continue

        if input_path.is_dir():
            if args.verbose:
                print(f"Including all JSP files in directory: {input_path}")
            files_to_process.extend(input_path.rglob("*.jsp"))
        elif input_path.is_file():
            if input_path.suffix.lower() == ".jsp":
                if args.verbose:
                    print(f"Including JSP file: {input_path}")
                files_to_process.append(input_path)
            else:
                print(
                    f"Warning: Skipping non-JSP file: {input_path}",
                    file=sys.stderr,
                )

    initial_count = len(files_to_process)
    files_to_process = [
        p
        for p in files_to_process
        if not any(p.match(pattern) for pattern in IGNORE_PATTERNS)
    ]

    if args.verbose:
        print(
            f"Found {initial_count} JSP files, "
            f"processing {len(files_to_process)} after ignoring excluded directories."
        )

    process_files(files_to_process, args.verbose)


if __name__ == "__main__":
    main()
