FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .

RUN uv pip install --system -e .

COPY src/ src/

ENV PYTHONPATH=/app/src

CMD ["python", "-m", "rag_core.sync"]
