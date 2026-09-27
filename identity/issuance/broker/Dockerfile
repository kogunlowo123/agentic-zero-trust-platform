FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

COPY broker.py .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
EXPOSE 8082

CMD ["uvicorn", "broker:app", "--host", "0.0.0.0", "--port", "8082"]
