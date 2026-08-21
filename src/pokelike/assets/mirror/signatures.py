"""Magic-byte validation for downloaded files.

In: file bytes and a suffix. Out: whether the content matches the format.

The site does NOT answer 404 for missing files: it returns index.html with
status 200. Without this check the mirror fills up with HTML pages wearing a
.png extension.
"""

from __future__ import annotations

# Magic numbers for binary formats.
SIGNATURES = {
    ".png": (b"\x89PNG",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF8",),
    ".webp": (b"RIFF",),
    ".mp3": (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"),
    ".ogg": (b"OggS",),
    ".woff": (b"wOFF",),
    ".woff2": (b"wOF2",),
}


def _valid_content(data: bytes, suffix: str) -> bool:
    """Checks whether raw bytes match the expected format for a file extension.

    In: the file content and the dot-prefixed suffix. Out: True if valid.
    """
    if not data:
        return False
    expected = SIGNATURES.get(suffix.lower())
    if expected is not None:
        return data.startswith(expected)
    return True
