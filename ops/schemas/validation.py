from typing import Literal, TypedDict


class ValidationResult(TypedDict):
    status: Literal["pass", "fail"]
    exit_code: int
    output: str
