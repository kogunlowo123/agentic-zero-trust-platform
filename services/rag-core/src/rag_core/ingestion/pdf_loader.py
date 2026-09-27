from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from rag_core.ingestion.loader_registry import BaseLoader, Document, registry


@registry.register(".pdf")
class PDFLoader(BaseLoader):
    """Loads text from PDF files page-by-page using pypdf."""

    def load(self, path: Path) -> list[Document]:
        """Extract text from every page of a PDF file.

        Each page becomes a separate :class:`Document` with page-number metadata.

        Args:
            path: Path to the PDF file on disk.

        Returns:
            List of Document objects, one per page, in reading order.
        """
        path = Path(path)
        reader = PdfReader(str(path))
        documents: list[Document] = []

        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            if not text:
                continue
            documents.append(
                Document(
                    content=text,
                    metadata={
                        "source_file": str(path),
                        "page_number": page_number,
                        "total_pages": len(reader.pages),
                        "file_name": path.name,
                    },
                )
            )

        return documents
