"""Entry point shim: ``python -m rag_core.sync``.

This module exists so the Dockerfile CMD ``["python", "-m", "rag_core.sync"]``
resolves correctly.  All implementation lives in
:mod:`rag_core.ingestion.sync`.
"""

from rag_core.ingestion.sync import main

if __name__ == "__main__":
    main()
