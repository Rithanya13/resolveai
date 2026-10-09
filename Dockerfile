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

# Run as an unprivileged user (k8s/api.yaml also enforces runAsNonRoot).
RUN useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin app
USER 1000

EXPOSE 8000

CMD ["uvicorn", "resolveai.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
