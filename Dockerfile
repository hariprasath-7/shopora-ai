FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && pip install .

COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

RUN mkdir -p /app/data && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
