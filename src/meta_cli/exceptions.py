class MetaCLIError(Exception):
    """Base exception for CLI errors."""


class ConfigError(MetaCLIError):
    """Raised when configuration cannot be loaded or validated."""


class APIError(MetaCLIError):
    """Raised when Meta API requests fail."""
