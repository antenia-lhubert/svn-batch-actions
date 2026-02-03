"""
EditorConfig-based encoding and line ending transformation patch.

Automatically transforms file encodings and line endings based on .editorconfig
configuration files found in the checked-out SVN project directories.
"""

import sys
from pathlib import Path
from typing import Optional, Set
import editorconfig
from charset_normalizer import from_path

# Standard ignore patterns (reuse from jsp_utf8.py)
IGNORE_PATTERNS = [
    "**/target/**/*",
    "**/.svn/**/*",
    "**/.idea/**/*",
    "**/.git/**/*",
    "**/node_modules/**/*",
    "**/__pycache__/**/*",
    "**/*.pyc",
]

# Encoding name normalization
ENCODING_ALIASES = {
    "utf-8": "utf-8",
    "utf8": "utf-8",
    "utf-8-bom": "utf-8-sig",  # Python's BOM-handling codec
    "utf-16be": "utf-16-be",
    "utf-16le": "utf-16-le",
    "utf16be": "utf-16-be",
    "utf16le": "utf-16-le",
    "latin1": "latin-1",
    "latin-1": "latin-1",
    "iso-8859-1": "latin-1",
    "iso8859-1": "latin-1",
    "windows-1252": "cp1252",
    "cp1252": "cp1252",
}

# Line ending mappings
LINE_ENDING_MAP = {
    "lf": "\n",
    "crlf": "\r\n",
    "cr": "\r",
}

# Fallback encodings for detection failures
FALLBACK_ENCODINGS = ["utf-8", "latin-1", "cp1252", "utf-16"]


def is_binary_file(file_path: Path, sample_size: int = 8192) -> bool:
    """
    Check if a file is binary by looking for null bytes.

    Args:
        file_path: Path to the file to check
        sample_size: Number of bytes to read for checking

    Returns:
        True if file appears to be binary, False if text
    """
    try:
        with open(file_path, "rb") as f:
            sample = f.read(sample_size)
            return b"\x00" in sample
    except IOError:
        # If we can't read it, treat as binary to be safe
        return True


def detect_encoding(file_path: Path) -> Optional[str]:
    """
    Detect the encoding of a file using charset-normalizer.

    Args:
        file_path: Path to the file to detect

    Returns:
        Normalized encoding name, or None if detection failed
    """
    try:
        # Get all candidates from charset_normalizer
        results = from_path(file_path)

        if results:
            # Get the best match
            best = results.best()
            if best and best.encoding:
                best_encoding = normalize_encoding_name(best.encoding)

                # Special handling for common misidentifications in Windows-based projects:
                # 1. Any cp12xx encoding (cp1250, cp1251, etc.) other than cp1252
                # 2. Any Mac encoding (mac_latin2, mac_roman, etc.)
                # Override with cp1252 (Windows-1252, Western European) which is by far
                # the most common in Windows-based Western projects. charset-normalizer
                # frequently misidentifies cp1252 as other similar encodings with limited samples.
                if (best_encoding.startswith("cp12") and best_encoding != "cp1252") or best_encoding.startswith("mac_"):
                    return "cp1252"

                return best_encoding
    except Exception:
        pass

    # Try fallback encodings
    for encoding in FALLBACK_ENCODINGS:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                f.read()
            return encoding
        except (UnicodeDecodeError, IOError):
            continue

    return None


def normalize_encoding_name(encoding: str) -> str:
    """
    Convert encoding names to standard Python codec names.

    Args:
        encoding: Raw encoding name from editorconfig or detection

    Returns:
        Normalized encoding name
    """
    encoding_lower = encoding.lower().strip()
    return ENCODING_ALIASES.get(encoding_lower, encoding_lower)


def normalize_line_endings(content: str, target: str) -> str:
    """
    Normalize line endings in text content.

    Args:
        content: Text content with any line endings
        target: Target line ending type ('lf', 'crlf', or 'cr')

    Returns:
        Content with normalized line endings
    """
    if target not in LINE_ENDING_MAP:
        return content

    # First unify all line endings to LF
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Then apply target line ending
    target_ending = LINE_ENDING_MAP[target]
    if target_ending != "\n":
        content = content.replace("\n", target_ending)

    return content


def has_utf8_bom(content_bytes: bytes) -> bool:
    """
    Check if bytes start with UTF-8 BOM.

    Args:
        content_bytes: Raw file content

    Returns:
        True if BOM present, False otherwise
    """
    return content_bytes.startswith(b"\xef\xbb\xbf")


def add_utf8_bom(content_bytes: bytes) -> bytes:
    """
    Add UTF-8 BOM to bytes if not present.

    Args:
        content_bytes: Raw file content

    Returns:
        Content with BOM prepended
    """
    if has_utf8_bom(content_bytes):
        return content_bytes
    return b"\xef\xbb\xbf" + content_bytes


def remove_utf8_bom(content_bytes: bytes) -> bytes:
    """
    Remove UTF-8 BOM from bytes if present.

    Args:
        content_bytes: Raw file content

    Returns:
        Content with BOM removed
    """
    if has_utf8_bom(content_bytes):
        return content_bytes[3:]
    return content_bytes


def transform_file_encoding(
    file_path: Path,
    target_charset: Optional[str],
    target_line_ending: Optional[str],
    verbose: bool
) -> bool:
    """
    Transform a file's encoding and/or line endings.

    Args:
        file_path: Path to the file to transform
        target_charset: Target encoding (None to skip encoding transformation)
        target_line_ending: Target line ending type (None to skip)
        verbose: Whether to print detailed progress

    Returns:
        True if file was modified, False otherwise
    """
    # Handle EditorConfig "unset" convention
    if target_charset and target_charset.lower().strip() == "unset":
        target_charset = None
    if target_line_ending and target_line_ending.lower().strip() == "unset":
        target_line_ending = None

    if not target_charset and not target_line_ending:
        return False

    try:
        # Detect current encoding
        current_encoding = detect_encoding(file_path)
        if not current_encoding:
            print(f"Warning: Could not detect encoding for {file_path}, skipping", file=sys.stderr)
            return False

        # Normalize target charset
        if target_charset:
            target_charset_normalized = normalize_encoding_name(target_charset)

            # Check if it's a supported encoding
            if target_charset_normalized not in ENCODING_ALIASES.values():
                # Try to use it anyway - Python might support it
                try:
                    "test".encode(target_charset_normalized)
                except LookupError:
                    print(f"Warning: Unsupported charset '{target_charset}' for {file_path}, skipping", file=sys.stderr)
                    return False
        else:
            target_charset_normalized = None

        # Check if transformation is needed
        needs_encoding_change = target_charset_normalized and current_encoding != target_charset_normalized
        needs_line_ending_change = target_line_ending is not None

        if not needs_encoding_change and not needs_line_ending_change:
            if verbose:
                print(f"  {file_path.name}: {current_encoding} (already correct)")
            return False

        # Read file content
        try:
            with open(file_path, "r", encoding=current_encoding) as f:
                content = f.read()
        except UnicodeDecodeError as e:
            print(f"Warning: Could not decode {file_path} with detected encoding {current_encoding}: {e}", file=sys.stderr)
            return False

        # Apply line ending normalization if needed
        if target_line_ending:
            content = normalize_line_endings(content, target_line_ending)

        # Determine output encoding
        output_encoding = target_charset_normalized if target_charset_normalized else current_encoding

        # Handle BOM for UTF-8
        needs_bom = output_encoding == "utf-8-sig"

        # Encode content
        try:
            if needs_bom:
                # utf-8-sig codec handles BOM automatically
                content_bytes = content.encode("utf-8-sig")
            else:
                content_bytes = content.encode(output_encoding if output_encoding != "utf-8-sig" else "utf-8")
                # Remove BOM if present and not wanted
                if output_encoding == "utf-8":
                    content_bytes = remove_utf8_bom(content_bytes)
        except UnicodeEncodeError as e:
            # Try with replace error handler
            print(f"Warning: Some characters in {file_path} cannot be encoded to {output_encoding}, using replacement characters", file=sys.stderr)
            try:
                if needs_bom:
                    content_bytes = content.encode("utf-8-sig", errors="replace")
                else:
                    content_bytes = content.encode(output_encoding if output_encoding != "utf-8-sig" else "utf-8", errors="replace")
                    if output_encoding == "utf-8":
                        content_bytes = remove_utf8_bom(content_bytes)
            except Exception as e2:
                print(f"Error: Could not encode {file_path}: {e2}", file=sys.stderr)
                return False

        # Write transformed content
        with open(file_path, "wb") as f:
            f.write(content_bytes)

        if verbose:
            changes = []
            if needs_encoding_change:
                changes.append(f"{current_encoding} -> {output_encoding}")
            if needs_line_ending_change:
                changes.append(f"line endings -> {target_line_ending}")
            print(f"  {file_path.name}: {', '.join(changes)} [OK]")

        return True

    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False


def should_ignore(file_path: Path, working_dir: Path) -> bool:
    """
    Check if a file should be ignored based on ignore patterns.

    Args:
        file_path: Path to check
        working_dir: Working directory root

    Returns:
        True if file should be ignored, False otherwise
    """
    try:
        relative_path = file_path.relative_to(working_dir)
        path_str = str(relative_path).replace("\\", "/")

        for pattern in IGNORE_PATTERNS:
            # Simple glob pattern matching
            if pattern.startswith("**/"):
                suffix = pattern[3:]
                if path_str.endswith(suffix.replace("*", "")):
                    return True
                if "**" in suffix:
                    parts = suffix.split("/**/*")
                    if len(parts) == 2 and parts[0] in path_str:
                        return True
            elif "*" in pattern:
                # Simple wildcard matching
                pattern_parts = pattern.replace("\\", "/").split("*")
                if all(part in path_str for part in pattern_parts if part):
                    return True
            elif path_str == pattern or path_str.endswith("/" + pattern):
                return True

        return False
    except ValueError:
        # File is not relative to working_dir
        return True


def has_editorconfig(working_dir: Path) -> bool:
    """
    Check if .editorconfig exists in the working directory tree.

    Args:
        working_dir: Root directory to check

    Returns:
        True if .editorconfig is found, False otherwise
    """
    # Check for .editorconfig file directly
    if (working_dir / ".editorconfig").exists():
        return True

    # Test by trying to get properties for a sample file
    try:
        test_file = working_dir / "test.txt"
        props = editorconfig.get_properties(str(test_file.absolute()))
        # If we get any properties back, there's an editorconfig somewhere
        return len(props) > 0
    except Exception:
        return False


def apply(working_dir: Path, verbose: bool = False) -> None:
    """
    Apply EditorConfig-based encoding and line ending transformations.

    This function scans all text files in the working directory and transforms
    their encoding and line endings according to .editorconfig rules found in
    the checked-out project.

    Args:
        working_dir: Root directory of the checked-out SVN project
        verbose: Whether to print detailed progress information
    """
    if verbose:
        print("\n=== Applying EditorConfig encoding transformation ===")

    # Check if .editorconfig exists in the project
    if not has_editorconfig(working_dir):
        if verbose:
            print("No .editorconfig found in checked-out project, skipping")
        return

    if verbose:
        print("Found .editorconfig in checked-out project directory")
        print("Scanning for files to process...")

    # Find all files in the working directory
    all_files = [f for f in working_dir.rglob("*") if f.is_file()]

    # Filter out ignored files
    files_to_process = [
        f for f in all_files
        if not should_ignore(f, working_dir)
    ]

    if verbose:
        print(f"Found {len(files_to_process)} files (excluding ignored patterns)")
        print("\nChecking encodings against .editorconfig rules...")

    modified_files: Set[Path] = set()
    binary_skipped = 0

    for file_path in files_to_process:
        # Skip binary files
        if is_binary_file(file_path):
            if verbose:
                print(f"Warning: Skipping {file_path.name} (binary file)")
            binary_skipped += 1
            continue

        # Get editorconfig properties for this file
        try:
            props = editorconfig.get_properties(str(file_path.absolute()))
        except Exception as e:
            if verbose:
                print(f"Warning: Could not get editorconfig properties for {file_path}: {e}", file=sys.stderr)
            continue

        # Extract relevant properties
        target_charset = props.get("charset")
        target_line_ending = props.get("end_of_line")

        # Normalize "unset" values to None (EditorConfig convention)
        if target_charset and target_charset.lower().strip() == "unset":
            target_charset = None
        if target_line_ending and target_line_ending.lower().strip() == "unset":
            target_line_ending = None

        # Skip if no relevant properties
        if not target_charset and not target_line_ending:
            continue

        # Transform the file
        if transform_file_encoding(file_path, target_charset, target_line_ending, verbose):
            modified_files.add(file_path)

    if verbose:
        if binary_skipped > 0:
            print(f"\nSkipped {binary_skipped} binary file(s)")

    print(f"\n=== EditorConfig encoding transformation complete: {len(modified_files)} file(s) modified ===")
