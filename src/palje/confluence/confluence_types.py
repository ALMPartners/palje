from enum import Enum


class ConfluencePageBodyFormat(Enum):
    """Confluence body format types."""

    NONE = None
    """No body format is specified. For no body content cases."""

    STORAGE = "storage"
    """Confluence Storage Format."""

    VIEW = "view"
    EXPORT = "export"
