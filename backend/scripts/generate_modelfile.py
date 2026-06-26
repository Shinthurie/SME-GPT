"""
Phase 4 — Generate Ollama Modelfile and register the fine-tuned model.

Usage:
    python backend/scripts/generate_modelfile.py <path/to/model.gguf>

Example:
    python backend/scripts/generate_modelfile.py C:\\models\\sme-gpt-llama3.Q4_K_M.gguf
"""

import subprocess
import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: python generate_modelfile.py <path/to/model.gguf>")
    sys.exit(1)

gguf_path = Path(sys.argv[1]).resolve()
if not gguf_path.exists():
    print(f"ERROR: File not found: {gguf_path}")
    sys.exit(1)

MODEL_NAME = "sme-gpt-llama3"

MODELFILE_CONTENT = f"""FROM {gguf_path}

SYSTEM \"\"\"You are SME-GPT, a financial document AI assistant for Sri Lankan small and medium enterprises.
You extract structured data from invoices, receipts, purchase orders, and delivery notes in English and Sinhala.
You output ONLY valid JSON when asked for extraction. You answer financial queries using only provided data.
Never invent numbers, document IDs, or company names.\"\"\"

PARAMETER temperature 0
PARAMETER num_predict 4096
PARAMETER stop "<|end_of_text|>"
PARAMETER stop "<|eot_id|>"
"""

output_dir = Path(__file__).resolve().parent.parent / "training_data"
modelfile_path = output_dir / "Modelfile"
modelfile_path.write_text(MODELFILE_CONTENT, encoding="utf-8")
print(f"Modelfile written: {modelfile_path}")

print(f"\nRegistering model '{MODEL_NAME}' with Ollama...")
result = subprocess.run(
    ["ollama", "create", MODEL_NAME, "-f", str(modelfile_path)],
    capture_output=True, text=True
)
if result.returncode == 0:
    print(f"Success! Model registered as '{MODEL_NAME}'.")
    print(f"\nNext steps:")
    print(f"  1. Test: ollama run {MODEL_NAME}")
    print(f"  2. Update backend/.env:  OLLAMA_MODEL={MODEL_NAME}")
    print(f"  3. Restart the backend server")
else:
    print(f"ERROR: {result.stderr}")
    print(f"Run manually:")
    print(f"  ollama create {MODEL_NAME} -f {modelfile_path}")
