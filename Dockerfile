FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PROFILE_CRAFT_DB=/data/profile_craft.db

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd --create-home appuser && mkdir -p /data && chown appuser /data
USER appuser
VOLUME ["/data"]

EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# Seed the database with demo data on first start, then launch the UI.
CMD ["sh", "-c", "[ -f \"$PROFILE_CRAFT_DB\" ] || python -m profile_craft.pipeline.etl data/sample_users.json --db \"$PROFILE_CRAFT_DB\" --rejects /data/rejects.jsonl; streamlit run app.py --server.address=0.0.0.0 --server.port=8501"]
