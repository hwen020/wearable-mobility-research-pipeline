FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATABASE_URL=sqlite:////var/lib/mobility/mobility.db
LABEL org.opencontainers.image.title="Wearable Mobility Research Pipeline" org.opencontainers.image.version="1.0.0"
WORKDIR /app
COPY requirements.txt docker-entrypoint.sh ./
RUN pip install --no-cache-dir -r requirements.txt && \
    groupadd --system mobility && useradd --system --gid mobility mobility && \
    install -d -o mobility -g mobility /var/lib/mobility
COPY app app
COPY migrations migrations
COPY alembic.ini alembic.ini
COPY static static
COPY data/synthetic_wearable.csv data/synthetic_wearable.csv
RUN chown mobility:mobility data data/synthetic_wearable.csv
USER mobility
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD ["python", "-c", "import os; from urllib.request import urlopen; urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/health', timeout=3).close()"]
CMD ["sh", "/app/docker-entrypoint.sh"]
