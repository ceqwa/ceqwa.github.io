from typing import TypedDict


class DocumentInput(TypedDict, total=False):
    source_document: str
    destination: str
    markdown: str
    markdown_destination: str
    title: str
    category: str
    date: str | None
