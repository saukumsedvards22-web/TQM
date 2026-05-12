FROM python:3.11-slim

# weasyprint system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
COPY templates/ templates/

RUN pip install --no-cache-dir -e .

# Non-root user
RUN useradd -m tqm && chown -R tqm:tqm /app
USER tqm

ENTRYPOINT ["tqm"]
CMD ["--help"]
