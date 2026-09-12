"""Run zero-dependency checks for HTML references and JSON syntax."""

import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.services.metadata import metadata_errors

ERRORS = []
JSON_RESOURCES = (
    Path("data/metadata.json"),
    Path("data/finances/finances.json"),
    Path("data/financials-dashboard.json"),
)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            if attributes["id"] in self.ids:
                ERRORS.append(f"duplicate id {attributes['id']!r}")
            self.ids.add(attributes["id"])
        for name in ("href", "src"):
            if name in attributes:
                self.refs.append(attributes[name])


def main(root=ROOT):
    ERRORS.clear()
    metadata = None
    for relative in JSON_RESOURCES:
        path = root / relative
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if relative == Path("data/metadata.json"):
                metadata = value
                ERRORS.extend(metadata_errors(value, root))
        except (OSError, json.JSONDecodeError) as error:
            ERRORS.append(f"{path}: invalid JSON: {error}")

    if metadata is None:
        ERRORS.append("data/metadata.json could not be loaded")

    for page in root.glob("*.html"):
        parser = PageParser()
        try:
            parser.feed(page.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            ERRORS.append(f"{page}: invalid HTML input: {error}")
            continue
        for reference in parser.refs:
            if not reference or reference.startswith(("#", "data:", "mailto:", "tel:")):
                continue
            parsed = urlparse(reference)
            if parsed.scheme or parsed.netloc:
                continue
            target, _ = urldefrag(reference)
            if not (page.parent / target).resolve().is_file():
                ERRORS.append(f"{page}: missing local reference {reference}")

    if ERRORS:
        print("Site validation failed:")
        for error in ERRORS:
            print(f"- {error}")
        return 1
    print("Site validation passed: JSON, HTML IDs, and local references")
    return 0


if __name__ == "__main__":
    sys.exit(main())
