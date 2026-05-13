FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
        "fastapi>=0.115.0" \
        "uvicorn[standard]>=0.32.0" \
        "pydantic>=2.9.0" \
        "eth-account>=0.13.0" \
        "eth-utils>=4.1.0"

COPY app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
