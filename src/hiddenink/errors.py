class HiddenInkError(Exception):
    """Base class for errors shown to users as a one-line message."""


class ScanError(HiddenInkError):
    """The file could not be read (damaged, password-protected, or malformed)."""


class UnsafeFile(HiddenInkError):
    """The file exceeds safety limits (size, zip bomb)."""


class UnsupportedFormat(HiddenInkError):
    """The file type is not supported yet."""


class ScanTimeout(HiddenInkError):
    """The scan took longer than the time limit."""
