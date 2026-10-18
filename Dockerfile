# syntax=docker/dockerfile:1
# Suggest IQ: Streamlit app (consulting + retail checkout). Build:  docker build -t suggest-iq .   Run:  see "Hosting" in README.md
#
# Stage 1 installs dependencies and builds every search index from resources/ (offline, ~1 minute).
# Stage 2 is the slim runtime: dependencies + code + the prebuilt indexes. Nothing is downloaded when the container starts.

FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1 EMBEDDING_MODE=hash
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# dependencies first so this layer is cached until a requirements file changes
COPY requirements.txt reqs/base.txt
COPY p1_orchestrator/requirements.txt reqs/p1.txt
COPY p2_tech_clinical/requirements.txt reqs/p2.txt
COPY p3_sec_csr/requirements.txt reqs/p3.txt
COPY p4_eval_ui/requirements.txt reqs/p4.txt
COPY retail_basket/requirements.txt reqs/retail.txt
RUN pip install -r reqs/base.txt -r reqs/p1.txt -r reqs/p2.txt -r reqs/p3.txt -r reqs/p4.txt -r reqs/retail.txt

COPY core core
COPY p1_orchestrator p1_orchestrator
COPY p2_tech_clinical p2_tech_clinical
COPY p3_sec_csr p3_sec_csr
COPY p4_eval_ui p4_eval_ui
COPY retail_basket retail_basket
COPY scripts scripts
COPY resources resources
RUN python scripts/prepare_data.py


FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH" \
    REAL_DOMAINS=all EMBEDDING_MODE=hash LLM_MODE=mock \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    RETAIL_ORDERS_LOG=/app/data/retail/orders_log.jsonl PORT=8501
WORKDIR /app
RUN useradd --create-home --uid 10001 app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/core core
COPY --from=builder /app/p1_orchestrator p1_orchestrator
COPY --from=builder /app/p2_tech_clinical p2_tech_clinical
COPY --from=builder /app/p3_sec_csr p3_sec_csr
COPY --from=builder /app/p4_eval_ui p4_eval_ui
COPY --from=builder /app/retail_basket retail_basket
COPY --from=builder /app/scripts scripts
COPY --from=builder /app/resources/Retail.zip resources/Retail.zip
COPY --from=builder /app/data/index data/index
COPY --from=builder /app/data/raw/retail data/raw/retail
COPY --from=builder /app/data/BUNDLE.json data/BUNDLE.json
# the only writable data: the retail order log. Mount a volume here to keep orders across restarts.
RUN mkdir -p data/retail data/eval && chown -R app:app data
USER app
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/_stcore/health' % os.getenv('PORT','8501'))"
CMD ["sh", "-c", "python -m p4_eval_ui.ui.launch --port ${PORT:-8501} --no-open"]
