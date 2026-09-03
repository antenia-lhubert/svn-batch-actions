"""Patch the root project version in a Maven pom.xml file."""

import re
from pathlib import Path
from xml.parsers import expat
from xml.sax.saxutils import escape


CONFIG_KEY = "pom_version"


def _local_name(name: str) -> str:
    return name.rsplit(":", 1)[-1]


def _start_tag_end(content: bytes, start: int) -> int:
    """Return the byte offset immediately after an XML start tag."""
    quote = None
    for index in range(start, len(content)):
        byte = content[index]
        if quote is not None:
            if byte == quote:
                quote = None
        elif byte in (ord('"'), ord("'")):
            quote = byte
        elif byte == ord(">"):
            return index + 1

    raise ValueError("Unterminated XML start tag in pom.xml")


def _find_project_version(content: bytes) -> tuple[int, int]:
    """Locate the text of the direct project/version element by byte offset."""
    parser = expat.ParserCreate()
    element_stack = []
    version_start = None
    version_ranges = []

    def start_element(name: str, _attributes: dict) -> None:
        nonlocal version_start
        element_stack.append(_local_name(name))
        if element_stack == ["project", "version"]:
            version_start = _start_tag_end(content, parser.CurrentByteIndex)
            if content[parser.CurrentByteIndex : version_start].rstrip().endswith(b"/>"):
                raise ValueError("The project <version> element in pom.xml cannot be self-closing")

    def end_element(_name: str) -> None:
        nonlocal version_start
        if element_stack == ["project", "version"] and version_start is not None:
            version_ranges.append((version_start, parser.CurrentByteIndex))
            version_start = None
        element_stack.pop()

    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element

    try:
        parser.Parse(content, True)
    except expat.ExpatError as error:
        raise ValueError(f"Invalid XML in pom.xml: {error}") from error

    if not version_ranges:
        raise ValueError("pom.xml does not define a direct project <version> element")
    if len(version_ranges) > 1:
        raise ValueError("pom.xml defines multiple direct project <version> elements")

    return version_ranges[0]


def apply(working_dir: Path, version: str, verbose: bool = False) -> None:
    """Replace the direct project version while preserving the rest of pom.xml."""
    pom_path = working_dir / "pom.xml"
    if not pom_path.is_file():
        raise FileNotFoundError(f"Maven POM not found: {pom_path}")

    content = pom_path.read_bytes()
    encoding_match = re.match(
        br"(?:\xef\xbb\xbf)?\s*<\?xml[^>]*encoding=[\"']([^\"']+)",
        content,
        re.IGNORECASE,
    )
    if encoding_match and encoding_match.group(1).lower() not in (b"utf-8", b"utf8"):
        raise ValueError("pom.xml must use UTF-8 encoding")

    try:
        content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("pom.xml must use UTF-8 encoding") from error

    start, end = _find_project_version(content)
    old_text = content[start:end].decode("utf-8")
    if "<" in old_text:
        raise ValueError("The project <version> element must contain text only")

    if old_text.strip():
        leading_length = len(old_text) - len(old_text.lstrip())
        trailing_length = len(old_text) - len(old_text.rstrip())
        leading = old_text[:leading_length]
        trailing = old_text[len(old_text) - trailing_length :] if trailing_length else ""
    else:
        leading = trailing = ""
    replacement = f"{leading}{escape(version)}{trailing}".encode("utf-8")

    if content[start:end] == replacement:
        if verbose:
            print(f"POM version is already {version}: {pom_path}")
        return

    pom_path.write_bytes(content[:start] + replacement + content[end:])
    if verbose:
        print(f"Updated POM version to {version}: {pom_path}")
