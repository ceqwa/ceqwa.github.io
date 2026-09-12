from typing import TypedDict


class ContentUpdate(TypedDict):
    path: str
    content: str
    expected_sha256: str
