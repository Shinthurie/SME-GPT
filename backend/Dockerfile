FROM python:3.12-slim

# System libraries the pipeline needs at runtime:
#   poppler-utils — pdf2image (PDF -> page images)
#   libglib2.0-0 / libgl1 — OpenCV (cv2) shared-object dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libglib2.0-0 \
    libgl1 \
 && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces runs the container as UID 1000 and expects a writable
# HOME for model/cache downloads. Running non-root is good practice on any host,
# so we do it everywhere, not just on Spaces.
RUN useradd -m -u 1000 appuser
USER appuser

ENV HOME=/home/appuser \
    PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    POPPLER_PATH=/usr/bin \
    HF_HOME=/home/appuser/.cache/huggingface

WORKDIR /home/appuser/app

COPY --chown=appuser:appuser requirements.txt .
# Generous timeout/retries so a slow network doesn't fail the build midway
# through a large wheel (PyTorch is ~800 MB).
RUN pip install --no-cache-dir --user --timeout 300 --retries 10 -r requirements.txt

# Bake the embedding model into the image so the first request doesn't stall on
# a ~470 MB download, and so it doesn't depend on ephemeral runtime storage.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"

COPY --chown=appuser:appuser . .

# 7860 is the Hugging Face Spaces default; other hosts (Cloud Run, Render) inject
# their own $PORT, which the shell-form CMD picks up.
EXPOSE 7860
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}
