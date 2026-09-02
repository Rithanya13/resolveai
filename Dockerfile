FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements-postgres.txt ./
RUN pip install --no-cache-dir -r requirements-postgres.txt

COPY src ./src
COPY evals ./evals

ENV PYTHONPATH=/app/src:/app
ENV RESOLVEAI_LLM_PROVIDER=fake
ENV RESOLVEAI_EMBEDDING_PROVIDER=fake
ENV RESOLVEAI_VECTOR_STORE=memory

EXPOSE 8000

CMD ["uvicorn", "resolveai.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
