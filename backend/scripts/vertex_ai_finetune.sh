#!/usr/bin/env bash
# =============================================================================
# Vertex AI Gemini Supervised Fine-Tuning — SME-GPT
# =============================================================================
# Prerequisites:
#   1. Google Cloud SDK installed: https://cloud.google.com/sdk/docs/install
#   2. A GCP project with Vertex AI API enabled
#   3. Training JSONL files generated: python scripts/generate_training_data.py
#   4. gcloud auth: run   gcloud auth login   and   gcloud auth application-default login
#
# Usage:
#   cd backend
#   bash scripts/vertex_ai_finetune.sh
#
# After completion:
#   - Each tuning job prints a MODEL_ENDPOINT_ID
#   - Set these in backend/.env:
#       GEMINI_TUNED_EXTRACTION_MODEL=tunedModels/<id>
#       GEMINI_TUNED_QUERY_MODEL=tunedModels/<id>
# =============================================================================

set -euo pipefail

# ── Configuration — edit these ───────────────────────────────────────────────

GCP_PROJECT="${GCP_PROJECT:-your-gcp-project-id}"
GCP_REGION="${GCP_REGION:-us-central1}"
GCS_BUCKET="${GCS_BUCKET:-gs://sme-gpt-training-data}"
BASE_MODEL="gemini-2.5-flash-002"

# Training data directory (relative to backend/)
TRAINING_DIR="$(dirname "$0")/../training_data"

# Tuning job display names
EXTRACTION_JOB_NAME="sme-gpt-extraction-$(date +%Y%m%d)"
CORRECTION_JOB_NAME="sme-gpt-correction-$(date +%Y%m%d)"
PLANNING_JOB_NAME="sme-gpt-planning-$(date +%Y%m%d)"
ANSWERING_JOB_NAME="sme-gpt-answering-$(date +%Y%m%d)"

# ── Colours ──────────────────────────────────────────────────────────────────

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }

# ── Step 0: Check prerequisites ───────────────────────────────────────────────

log "Checking prerequisites..."

if ! command -v gcloud &>/dev/null; then
  echo "ERROR: gcloud CLI not found. Install from https://cloud.google.com/sdk/docs/install"
  exit 1
fi

if ! command -v gsutil &>/dev/null; then
  echo "ERROR: gsutil not found (usually bundled with gcloud). Run: gcloud components install gsutil"
  exit 1
fi

# Ensure training data exists
for task in extraction correction planning answering; do
  f="${TRAINING_DIR}/gemini_${task}.jsonl"
  if [[ ! -f "$f" ]]; then
    echo "ERROR: Missing training file: $f"
    echo "       Run first: python scripts/generate_training_data.py"
    exit 1
  fi
  count=$(wc -l < "$f")
  log "  gemini_${task}.jsonl — ${count} examples"
done

# ── Step 1: Set up GCP project ────────────────────────────────────────────────

log "Setting GCP project: $GCP_PROJECT"
gcloud config set project "$GCP_PROJECT"
gcloud config set compute/region "$GCP_REGION"

# Enable required APIs (idempotent)
log "Enabling Vertex AI API..."
gcloud services enable aiplatform.googleapis.com --quiet

# ── Step 2: Create GCS bucket and upload training data ───────────────────────

log "Creating GCS bucket (if not exists): $GCS_BUCKET"
gsutil mb -p "$GCP_PROJECT" -l "$GCP_REGION" "$GCS_BUCKET" 2>/dev/null || warn "Bucket already exists."

log "Uploading training JSONL files..."
gsutil -m cp "${TRAINING_DIR}/gemini_extraction.jsonl"  "${GCS_BUCKET}/extraction/"
gsutil -m cp "${TRAINING_DIR}/gemini_correction.jsonl"  "${GCS_BUCKET}/correction/"
gsutil -m cp "${TRAINING_DIR}/gemini_planning.jsonl"    "${GCS_BUCKET}/planning/"
gsutil -m cp "${TRAINING_DIR}/gemini_answering.jsonl"   "${GCS_BUCKET}/answering/"
ok "Training data uploaded to $GCS_BUCKET"

# ── Step 3: Submit tuning jobs ────────────────────────────────────────────────
# Note: Vertex AI supervised fine-tuning for Gemini is done via the REST API or
# Python SDK (gcloud CLI doesn't yet have first-class support for Gemini tuning).
# The Python SDK approach below uses google-cloud-aiplatform.
#
# Install if needed: pip install google-cloud-aiplatform>=1.38.0

log "Submitting tuning jobs via Python SDK..."

python3 - <<'PYEOF'
import os, sys, time
try:
    from google.cloud import aiplatform
    from google.cloud.aiplatform.preview.language_models import TextGenerationModel
except ImportError:
    print("ERROR: google-cloud-aiplatform not installed.")
    print("       Run: pip install google-cloud-aiplatform>=1.38.0")
    sys.exit(1)

PROJECT    = os.environ.get("GCP_PROJECT", "your-gcp-project-id")
REGION     = os.environ.get("GCP_REGION",  "us-central1")
BUCKET     = os.environ.get("GCS_BUCKET",  "gs://sme-gpt-training-data")
BASE_MODEL = "gemini-2.5-flash-002"

aiplatform.init(project=PROJECT, location=REGION)

TASKS = [
    {
        "name":       "extraction",
        "display":    f"sme-gpt-extraction-{int(time.time())}",
        "train_uri":  f"{BUCKET}/extraction/gemini_extraction.jsonl",
        "epochs":     5,
        "lr_mult":    1.0,
    },
    {
        "name":       "planning",
        "display":    f"sme-gpt-planning-{int(time.time())}",
        "train_uri":  f"{BUCKET}/planning/gemini_planning.jsonl",
        "epochs":     8,
        "lr_mult":    1.0,
    },
    {
        "name":       "answering",
        "display":    f"sme-gpt-answering-{int(time.time())}",
        "train_uri":  f"{BUCKET}/answering/gemini_answering.jsonl",
        "epochs":     5,
        "lr_mult":    0.5,
    },
    {
        "name":       "correction",
        "display":    f"sme-gpt-correction-{int(time.time())}",
        "train_uri":  f"{BUCKET}/correction/gemini_correction.jsonl",
        "epochs":     5,
        "lr_mult":    1.0,
    },
]

submitted = []
for t in TASKS:
    print(f"  Submitting {t['name']} tuning job: {t['display']}")
    try:
        job = aiplatform.PipelineJob.from_pretrained(
            model_name=BASE_MODEL,
        )
        # Use the supervised tuning API directly
        from google.cloud.aiplatform import initializer
        from google.cloud.aiplatform_v1beta1.services.gen_ai_tuning_service import GenAiTuningServiceClient
        from google.cloud.aiplatform_v1beta1.types import TuningJob, SupervisedTuningSpec

        client = GenAiTuningServiceClient(
            client_options={"api_endpoint": f"{REGION}-aiplatform.googleapis.com"}
        )
        parent = f"projects/{PROJECT}/locations/{REGION}"
        tuning_job = TuningJob(
            base_model=f"publishers/google/models/{BASE_MODEL}",
            supervised_tuning_spec=SupervisedTuningSpec(
                training_dataset_uri=t["train_uri"],
                hyper_parameters={
                    "epoch_count": t["epochs"],
                    "learning_rate_multiplier": t["lr_mult"],
                },
            ),
            tuned_model_display_name=t["display"],
        )
        response = client.create_tuning_job(parent=parent, tuning_job=tuning_job)
        submitted.append({"task": t["name"], "job_name": response.name})
        print(f"    ✓ Job submitted: {response.name}")
    except Exception as e:
        print(f"    ✗ Failed to submit {t['name']}: {e}")

print("\n" + "="*60)
print("SUBMITTED JOBS:")
for s in submitted:
    print(f"  {s['task']:12s}: {s['job_name']}")
print()
print("Monitor jobs at:")
print(f"  https://console.cloud.google.com/vertex-ai/training/custom-jobs?project={PROJECT}")
print()
print("When complete, set in backend/.env:")
print("  GEMINI_TUNED_EXTRACTION_MODEL=<extraction model endpoint>")
print("  GEMINI_TUNED_QUERY_MODEL=<planning model endpoint>")
PYEOF

# ── Step 4: Print monitoring instructions ─────────────────────────────────────

echo ""
ok "Fine-tuning jobs submitted."
echo ""
echo "========================================================================"
echo "  NEXT STEPS"
echo "========================================================================"
echo ""
echo "1. Monitor job progress (10-60 min per job):"
echo "   https://console.cloud.google.com/vertex-ai/generative/language/tuning"
echo ""
echo "2. When EACH JOB completes, retrieve the tuned model endpoint ID:"
echo "   gcloud ai tuning-jobs list --region=$GCP_REGION --project=$GCP_PROJECT"
echo ""
echo "3. Add the tuned model IDs to backend/.env:"
echo "   GEMINI_TUNED_EXTRACTION_MODEL=tunedModels/<extraction-job-id>"
echo "   GEMINI_TUNED_QUERY_MODEL=tunedModels/<planning-job-id>"
echo ""
echo "4. Restart the backend:"
echo "   uvicorn app:app --reload --port 8000"
echo ""
echo "5. Verify Gemini is active:"
echo "   curl -s http://localhost:8000/health | python -m json.tool"
echo "   (Look for \"llm_provider\": \"gemini\" in the response)"
echo ""
echo "========================================================================"
echo "  COST ESTIMATE (gemini-2.5-flash supervised tuning)"
echo "========================================================================"
echo ""
echo "  - Base charge: ~\$0.002 per 1K training tokens"
echo "  - Extraction job (~200 examples × 500 tokens): ~\$0.20"
echo "  - Planning job   (~150 examples × 300 tokens): ~\$0.09"
echo "  - Answering job  (~200 examples × 400 tokens): ~\$0.16"
echo "  - Correction job (~100 examples × 600 tokens): ~\$0.12"
echo "  Total estimated: ~\$0.60 for all 4 jobs"
echo ""
echo "  Tuned model inference: \$0.075/1M input tokens + \$0.30/1M output tokens"
echo "  (See: https://cloud.google.com/vertex-ai/generative-ai/pricing)"
echo ""
