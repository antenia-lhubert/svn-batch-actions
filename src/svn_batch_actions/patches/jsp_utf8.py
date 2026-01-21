"""JSP UTF-8 header patch.

Adds UTF-8 encoding headers to JSP files and applies targeted replacements.
This patch:
- Removes existing contentType directives and meta tags
- Adds standard UTF-8 contentType directive
- Applies targeted replacements for JDBC, web.xml, etc.
"""

import re
import sys
from pathlib import Path


# Page directive configuration
NEW_PAGE_CONTENT_TYPE_DIRECTIVE = '<%@page contentType="text/html;charset=UTF-8"%>'

EXISTING_PAGE_CONTENT_TYPE_REGEX = re.compile(r"<\s*%\s*@\s*page[^%]*contentType\s?=[^%]*%\s*>", re.IGNORECASE)

# Removal patterns
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

# Patterns to ignore
IGNORE_PATTERNS = [
    "**/target/**/*",
    "**/.svn/**/*",
    "**/.idea/**/*",
    "**/.git/**/*",
    "**/node_modules/**/*",
]

# Targeted replacements for specific files
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


def _process_jsp_files(files_to_process: list[Path], verbose: bool) -> set[Path]:
    """
    Process JSP files by removing existing encoding directives and adding UTF-8.

    Args:
        files_to_process: List of JSP file paths to process
        verbose: Enable verbose output

    Returns:
        Set of modified file paths
    """
    if not files_to_process:
        if verbose:
            print("No JSP files found to process")
        return set()

    modified_files = set()

    if verbose:
        print("Removing existing contentType directives and meta tags from JSP files...")

    for file_path in files_to_process:
        try:
            original_content = file_path.read_text(encoding="latin1")
            content = original_content

            # Remove existing encoding directives
            content = REMOVAL_PAGE_DIRECTIVE_REGEX.sub("", content)
            content = REMOVAL_META_HTTP_EQUIV_REGEX.sub("", content)
            content = REMOVAL_META_CHARSET_REGEX.sub("", content)
            content = REMOVAL_FORM_ACCEPT_CHARSET_REGEX.sub(r"\1", content)

            # Remove all leading whitespace
            content = content.lstrip()

            # Add UTF-8 directive if not already present
            if not EXISTING_PAGE_CONTENT_TYPE_REGEX.search(content):
                content = NEW_PAGE_CONTENT_TYPE_DIRECTIVE + "\n" + content

            if content != original_content:
                if verbose:
                    print(f"  Modified: {file_path}")
                modified_files.add(file_path)
                file_path.write_text(content, encoding="latin1")

        except (IOError, UnicodeDecodeError) as e:
            print(f"  Error processing file {file_path}: {e}", file=sys.stderr)

    if verbose:
        if modified_files:
            print(f"  Total JSP files modified: {len(modified_files)}")
        else:
            print("  No JSP files were modified")

    return modified_files


def _apply_targeted_replacements(base_path: Path, verbose: bool) -> set[Path]:
    """
    Apply targeted regex replacements to specific files.

    Args:
        base_path: Root directory to search for files
        verbose: Enable verbose output

    Returns:
        Set of modified file paths
    """
    if not TARGETED_REPLACEMENTS:
        return set()

    if verbose:
        print("Applying targeted regex replacements...")

    modified_files = set()

    for replacement_config in TARGETED_REPLACEMENTS:
        file_pattern = replacement_config["file_pattern"]
        regex = replacement_config["regex"]
        replacement = replacement_config["replacement"]
        description = replacement_config.get("description", "No description provided")

        if verbose:
            print(f"  Processing: {description}")
            print(f"    Pattern: {file_pattern}")

        matching_files = list(base_path.rglob(file_pattern))

        for file_path in matching_files:
            # Skip ignored paths
            if any(file_path.match(pattern) for pattern in IGNORE_PATTERNS):
                continue

            try:
                original_content = file_path.read_text(encoding="latin1")
                content = regex.sub(replacement, original_content)

                if content != original_content:
                    if verbose:
                        print(f"    Modified: {file_path}")
                    modified_files.add(file_path)
                    file_path.write_text(content, encoding="latin1")

            except (IOError, UnicodeDecodeError) as e:
                print(f"  Error processing file {file_path}: {e}", file=sys.stderr)

    if verbose:
        if modified_files:
            print(f"  Targeted replacements modified {len(modified_files)} file(s)")
        else:
            print("  No files were modified by targeted replacements")

    return modified_files


def apply(working_dir: Path, verbose: bool = False) -> None:
    """
    Apply JSP UTF-8 header patch to all JSP files in working directory.

    This patch performs the following operations:
    1. Finds all JSP files (excluding ignored directories)
    2. Removes existing contentType directives and meta tags
    3. Adds standard UTF-8 contentType directive
    4. Applies targeted replacements for JDBC, web.xml, etc.

    Args:
        working_dir: Root directory to search for JSP files
        verbose: Enable verbose output

    Raises:
        Exception: If patch application fails
    """
    try:
        if verbose:
            print("=== Applying JSP UTF-8 header patch ===")

        # Find all JSP files
        jsp_files = list(working_dir.rglob("*.jsp"))

        if verbose:
            print(f"Found {len(jsp_files)} JSP files")

        # Filter out ignored patterns
        files_to_process = [
            p for p in jsp_files
            if not any(p.match(pattern) for pattern in IGNORE_PATTERNS)
        ]

        if verbose:
            if len(files_to_process) < len(jsp_files):
                print(f"Processing {len(files_to_process)} JSP files (after filtering)")

        # Process JSP files
        jsp_modified = _process_jsp_files(files_to_process, verbose)

        # Apply targeted replacements
        targeted_modified = _apply_targeted_replacements(working_dir, verbose)

        # Summary
        total_modified = jsp_modified | targeted_modified
        if verbose:
            print(f"=== JSP UTF-8 patch complete: {len(total_modified)} file(s) modified ===")

    except Exception as e:
        raise Exception(f"JSP UTF-8 patch failed: {e}") from e
