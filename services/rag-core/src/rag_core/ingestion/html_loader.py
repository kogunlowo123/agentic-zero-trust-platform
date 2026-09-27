from __future__ import annotations

import re
from pathlib import Path

import httpx
from bs4 import BeautifulSoup, NavigableString

from rag_core.ingestion.loader_registry import BaseLoader, Document, registry


_STRIP_TAGS = {
    "nav", "header", "footer", "aside", "script", "style", "noscript",
    "form", "button", "input", "select", "textarea", "iframe", "meta",
    "link",
}

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


def _is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _fetch_url(url: str) -> str:
    response = httpx.get(url, follow_redirects=True, timeout=30)
    response.raise_for_status()
    return response.text


def _parse_html(raw_html: str, source_label: str) -> list[Document]:
    soup = BeautifulSoup(raw_html, "html.parser")

    # Remove noisy structural elements.
    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()

    documents: list[Document] = []
    current_headings: dict[str, str] = {}
    current_texts: list[str] = []

    def flush(headings: dict[str, str]) -> None:
        text = " ".join(current_texts).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            documents.append(
                Document(
                    content=text,
                    metadata={
                        "source_file": source_label,
                        "headings": dict(headings),
                    },
                )
            )
        current_texts.clear()

    body = soup.find("body") or soup
    for element in body.descendants:
        if element.name in _HEADING_TAGS:
            flush(current_headings)
            heading_text = element.get_text(separator=" ", strip=True)
            current_headings[element.name] = heading_text
        elif isinstance(element, NavigableString):
            text = str(element).strip()
            if text:
                current_texts.append(text)

    flush(current_headings)
    return documents


@registry.register(".html")
class HTMLLoader(BaseLoader):
    """Loads text from HTML files or URLs using BeautifulSoup4.

    Navigation elements, headers, footers and scripts are stripped.
    Heading tags are recorded as metadata on each resulting Document.
    """

    def load(self, path: Path | str) -> list[Document]:  # type: ignore[override]
        """Load an HTML document from a file path or URL.

        Args:
            path: A :class:`pathlib.Path` to a local file, or a URL string.

        Returns:
            List of Document objects, one per logical content section.
        """
        raw: str
        source_label: str

        if isinstance(path, str) and _is_url(path):
            raw = _fetch_url(path)
            source_label = path
        else:
            path = Path(path)
            raw = path.read_text(encoding="utf-8", errors="replace")
            source_label = str(path)

        return _parse_html(raw, source_label)
