"""Machine-readable errors returned by the CEQWA administration API."""


class CeqwaError(Exception):
    """An expected, safe-to-expose administration error."""

    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict:
        return {"success": False, "error_code": self.code, "message": self.message, "details": self.details}


def require(condition: bool, code: str, message: str, details: dict | None = None) -> None:
    if not condition:
        raise CeqwaError(code, message, details)
