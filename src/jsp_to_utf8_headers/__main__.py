import argparse
import re
import sys
from pathlib import Path

NEW_PAGE_CONTENT_TYPE_DIRECTIVE = '<%@page contentType="text/html;charset=UTF-8"%>'

EXISTING_PAGE_CONTENT_TYPE_REGEX = re.compile(r"<\s*%\s*@\s*page[^%]*contentType\s?=[^%]*%\s*>", re.IGNORECASE)

REMOVAL_PAGE_DIRECTIVE_REGEX = re.compile(
    r"[ \t\f]*<%\s*@\s*page[^%]*contentType\s?=(?:(?!xml)[^%])*%>\s*[\r\n]*",
    re.IGNORECASE,
)

REMOVAL_META_HTTP_EQUIV_REGEX = re.compile(
    r'[ \t\f]*<meta[^>]*http-equiv=["\']?Content-Type[^>]*>[\r\n]*',
    re.IGNORECASE,
)

REMOVAL_META_CHARSET_REGEX = re.compile(r'[ \t\f]*<meta[^>]*charset=["\']?[^>]*>[\r\n]*', re.IGNORECASE)

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

TARGETED_REPLACEMENTS = [
    {
        "file_pattern": "src/com/leaderinfo/novanet/commons/ParametrageNovanet.java",
        "regex": re.compile(r"&characterEncoding=latin1"),
        "replacement": "&characterEncoding=UTF-8&connectionCollation=utf8mb4_0900_ai_ci",
        "description": "Fix JDBC connection encoding"
    },
    {
        "file_pattern": "novanet/WEB-INF/web.xml",
        "regex": re.compile(r"""<display-name>novanet</display-name>
	
	<context-param>"""),
        "replacement": """<display-name>novanet</display-name>

    <filter>
        <filter-name>UTF_8_characterEncodingFilter</filter-name>
        <filter-class>org.springframework.web.filter.CharacterEncodingFilter</filter-class>
        <init-param>
            <param-name>encoding</param-name>
            <param-value>UTF-8</param-value>
        </init-param>
        <init-param>
            <param-name>forceEncoding</param-name>
            <param-value>false</param-value>
        </init-param>
    </filter>
    <filter-mapping>
        <filter-name>UTF_8_characterEncodingFilter</filter-name>
        <url-pattern>/*</url-pattern>
    </filter-mapping>
    
    <context-param>""",
        "description": "Add web.xml character encoding filter"
    },
    {
        "file_pattern": "novanet/WEB-INF/web.xml",
        "regex": re.compile(r"<page-encoding>ISO-8859-1</page-encoding>"),
        "replacement": "<page-encoding>WINDOWS-1252</page-encoding>",
        "description": "set web.xml JSP processing to WINDOWS-1252"
    },
]


def process_files(files_to_process: list[Path], verbose: bool):
    if not files_to_process:
        print("No valid JSP files or directories found to process.")
        return

    modified_files = set()

    print("Removing existing contentType directives and meta tags from JSP files...")

    for file_path in files_to_process:
        try:
            original_content = file_path.read_text(encoding="latin1")
            content = original_content

            content = REMOVAL_PAGE_DIRECTIVE_REGEX.sub("", content)
            content = REMOVAL_META_HTTP_EQUIV_REGEX.sub("", content)
            content = REMOVAL_META_CHARSET_REGEX.sub("", content)
            content = REMOVAL_FORM_ACCEPT_CHARSET_REGEX.sub(r"\1", content)

            # Remove all leading whitespace (the removal regexes handle trailing whitespace)
            content = content.lstrip()

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


def apply_targeted_replacements(base_path: Path, verbose: bool):
    if not TARGETED_REPLACEMENTS:
        return

    print("\nApplying targeted regex replacements...")
    modified_files = set()

    for replacement_config in TARGETED_REPLACEMENTS:
        file_pattern = replacement_config["file_pattern"]
        regex = replacement_config["regex"]
        replacement = replacement_config["replacement"]
        description = replacement_config.get("description", "No description provided")

        if verbose:
            print(f"\nProcessing replacement: {description}")
            print(f"  Pattern: {file_pattern}")

        matching_files = list(base_path.rglob(file_pattern))

        for file_path in matching_files:
            if any(file_path.match(pattern) for pattern in IGNORE_PATTERNS):
                continue

            try:
                original_content = file_path.read_text(encoding="latin1")
                content = regex.sub(replacement, original_content)

                if content != original_content:
                    if verbose:
                        print(f"  Modified: {file_path}")
                    modified_files.add(file_path)
                    file_path.write_text(content, encoding="latin1")

            except (IOError, UnicodeDecodeError) as e:
                print(f"Error processing file {file_path}: {e}", file=sys.stderr)

    if modified_files:
        print(f"\nTargeted replacements modified {len(modified_files)} file(s).")
    elif verbose:
        print("\nNo files were modified by targeted replacements.")


def main():
    parser = argparse.ArgumentParser(description="Process JSP files to standardize page contentType directives.")
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
    files_to_process = [p for p in files_to_process if not any(p.match(pattern) for pattern in IGNORE_PATTERNS)]

    if args.verbose:
        print(
            f"Found {initial_count} JSP files, "
            f"processing {len(files_to_process)} after ignoring excluded directories."
        )

    process_files(files_to_process, args.verbose)

    for input_path_str in args.paths:
        input_path = Path(input_path_str).resolve()
        if input_path.exists():
            base_path = input_path if input_path.is_dir() else input_path.parent
            apply_targeted_replacements(base_path, args.verbose)


if __name__ == "__main__":
    main()
