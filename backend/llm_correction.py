import os
import re
import requests
from pathlib import Path
from symspellpy import SymSpell, Verbosity

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_HOST = "https://api.deepseek.com"

BASE_DIR = Path(__file__).resolve().parent
DICT_DIR = BASE_DIR / "dictionaries"

sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)

CUSTOM_ENGLISH_TERMS = set()
CUSTOM_SINHALA_TERMS = set()

ENGLISH_CORRECTIONS = {
    "invioce": "invoice",
    "invoce": "invoice",
    "invoie": "invoice",
    "reciept": "receipt",
    "recipt": "receipt",
    "prnter": "printer",
    "papre": "paper",
    "payble": "payable",
    "toatl": "total",
    "amunt": "amount",
    "devces": "devices",
    "keybaord": "keyboard",
    "quatity": "quantity",
    "quanity": "quantity",
    "suplier": "supplier",
    "custmer": "customer",
    "delivary": "delivery",
    "harecut": "hair cut",
    "haircut": "hair cut",
    "saloon": "salon",
    "ammount": "amount",
    "balnce": "balance",
    "subtoatl": "subtotal",
    "discont": "discount",
    "adress": "address",
    "telepone": "telephone",
    "adresss": "address",
    "expence": "expense",
    "recievable": "receivable",
    "paymant": "payment",
    "totl": "total",
    "transpot": "transport",
    "restaurent": "restaurant",
    "statonary": "stationery",
}

SINHALA_CORRECTIONS = {
    "ඇනවුම": "ඇණවුම",
    "මුලු": "මුළු",
    "ඉන්වොය්ස්": "ඉන්වොයිස්",
    "ඉන්වොයස්": "ඉන්වොයිස්",
    "ඉන්වොයිස": "ඉන්වොයිස්",
    "වටිනාකම්": "වටිනාකම",
    "මුදල": "මුදල්",
    "ලැබියයුතු": "ලැබිය යුතු",
    "ගෙවියයුතු": "ගෙවිය යුතු",
    "ප්රමාණය": "ප්‍රමාණය",
    "මුලු එකතුව": "මුළු එකතුව",
}


def load_custom_terms():
    english_path = DICT_DIR / "english_domain_terms.txt"
    sinhala_path = DICT_DIR / "sinhala_common_5000.txt"

    if english_path.exists():
        with open(english_path, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if word:
                    CUSTOM_ENGLISH_TERMS.add(word.lower())
                    sym_spell.create_dictionary_entry(word.lower(), 10)

    if sinhala_path.exists():
        with open(sinhala_path, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if word:
                    CUSTOM_SINHALA_TERMS.add(word)


load_custom_terms()


def clean_ocr_text(text: str) -> str:
    if not isinstance(text, str):
        return ""

    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"[^\S\n]*[\*\|\~`]+[^\S\n]*", " ", text)
    return text.strip()

def count_sinhala_chars(text: str) -> int:
    if not isinstance(text, str):
        return 0
    return len(re.findall(r"[\u0D80-\u0DFF]", text))


def looks_like_transliterated_sinhala(original_text: str, corrected_text: str) -> bool:
    """
    If original had Sinhala but corrected lost most Sinhala chars,
    assume the model transliterated/translated incorrectly.
    """
    if not isinstance(original_text, str) or not isinstance(corrected_text, str):
        return False

    original_si = count_sinhala_chars(original_text)
    corrected_si = count_sinhala_chars(corrected_text)

    if original_si >= 8 and corrected_si < max(2, int(original_si * 0.3)):
        return True

    return False

def preserve_sensitive_tokens(text: str):
    if not isinstance(text, str):
        return "", {}

    pattern = r"""
    (
        \b\d[\d,./:-]*\b |
        \b[A-Z]{2,}\d+\b |
        \bDOC\d+\b |
        \bNEW\S*\b |
        \bINV\S*\b |
        \bPO\S*\b |
        \bDN\S*\b |
        \bREC\S*\b |
        \b[A-Z0-9\-_/]{4,}\b |
        \b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b |
        \b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b
    )
    """
    matches = re.findall(pattern, text, flags=re.VERBOSE)

    placeholders = {}
    masked = text

    for i, token in enumerate(matches):
        placeholder = f"__TOKEN_{i}__"
        placeholders[placeholder] = token
        masked = masked.replace(token, placeholder, 1)

    return masked, placeholders


def restore_sensitive_tokens(text: str, placeholders: dict):
    if not isinstance(text, str):
        return ""

    for placeholder, original in placeholders.items():
        text = text.replace(placeholder, original)

    return text

def looks_like_bad_rewrite(original_text: str, corrected_text: str) -> bool:
    if not isinstance(original_text, str) or not isinstance(corrected_text, str):
        return False

    original_lines = [ln for ln in original_text.splitlines() if ln.strip()]
    corrected_lines = [ln for ln in corrected_text.splitlines() if ln.strip()]

    # If OCR had multiple lines but corrected output collapsed too much, reject it
    if len(original_lines) >= 5 and len(corrected_lines) <= 2:
        return True

    # Reject if model output starts with chatty phrases
    bad_starts = [
        "i'll correct",
        "here's the corrected",
        "here is the corrected",
        "based on your attempt",
        "please let me know",
    ]
    lower = corrected_text.strip().lower()
    if any(lower.startswith(x) for x in bad_starts):
        return True

    return False

def strip_llm_boilerplate(text: str) -> str:
    if not isinstance(text, str):
        return ""

    replacements = [
        "I'll correct the OCR text while following the strict rules. Here's the corrected text:",
        "Here’s the corrected text:",
        "Here's the corrected text:",
        "Corrected OCR:",
        "Corrected OCR Text:",
        "Here is the corrected text:",
        "Corrected Text:",
        "Here is the cleaned text:",
        "Here is the corrected OCR text:",
    ]

    for r in replacements:
        text = text.replace(r, "").strip()

    cutoff_markers = [
        "\nNote:",
        "\nExplanation:",
        "\nI only corrected",
        "\nI corrected",
        "\nThis text",
        "\nLet me know",
        "\nBased on your attempt",
        "\nPlease let me know",
        "\nOnce I have the corrected text",
    ]

    for marker in cutoff_markers:
        if marker in text:
            text = text.split(marker)[0].strip()

    return text.strip()


# ── Iteration 2: numeric safeguard + per-box correction ──────────────────────

def extract_digit_sequences(text: str) -> list:
    """Return all digit-only runs in order — used to verify numeric immutability."""
    if not isinstance(text, str):
        return []
    return re.findall(r'\d+', text)


def safe_correct(original: str, corrected: str) -> str:
    """Return corrected text only if digit sequences are unchanged; else return original.

    Research §9.2: a correction that alters any number is always rejected so that
    amounts, dates, IDs, and quantities are never silently modified by the LLM.
    """
    if not isinstance(original, str):
        return original
    if not isinstance(corrected, str):
        return original
    if extract_digit_sequences(original) != extract_digit_sequences(corrected):
        return original
    return corrected


def correct_box(box: dict) -> dict:
    """Apply safe dictionary correction to one OCR text_line box.

    Returns a new dict with the corrected text and provenance fields:
      text          — corrected text (or original if digits would change)
      bbox          — from original box
      confidence    — from original box
      locked_digits — digit sequences extracted from the original text
      source        — 'dict' if dictionary correction changed anything, else 'original'
      polygon       — from original box (pass-through)
    """
    text = box.get("text", "") or ""
    locked_digits = extract_digit_sequences(text)

    dict_corrected = dictionary_correct_text(text)
    final_text = safe_correct(text, dict_corrected)

    return {
        "text": final_text,
        "bbox": box.get("bbox"),
        "confidence": box.get("confidence"),
        "locked_digits": locked_digits,
        "source": "dict" if final_text != text else "original",
        "polygon": box.get("polygon"),
    }


def correct_boxes_for_page(text_lines: list) -> list:
    """Apply box-level safe correction to all text lines of a page."""
    return [correct_box(b) for b in (text_lines or [])]


def _edit_distance(a: str, b: str) -> int:
    n = len(b)
    dp = list(range(n + 1))
    for i, ca in enumerate(a, 1):
        prev, dp[0] = dp[0], i
        for j, cb in enumerate(b, 1):
            prev, dp[j] = dp[j], min(prev + (ca != cb), dp[j] + 1, dp[j - 1] + 1)
    return dp[n]


def compute_cer(original: str, corrected: str) -> float:
    """Character Error Rate = edit_distance / len(original). 0.0 is perfect."""
    if not original:
        return 0.0
    return round(_edit_distance(original, corrected) / len(original), 4)


def compute_nar(boxes: list) -> float:
    """Numeric Accuracy Rate = fraction of boxes where digit sequences are preserved."""
    if not boxes:
        return 1.0
    preserved = sum(
        1 for b in boxes
        if extract_digit_sequences(b.get("text", "")) == b.get("locked_digits", [])
    )
    return round(preserved / len(boxes), 4)


# ─────────────────────────────────────────────────────────────────────────────

def correct_english_token_with_symspell(word: str) -> str:
    if not word:
        return word

    prefix = ""
    suffix = ""

    while word and not word[0].isalnum():
        prefix += word[0]
        word = word[1:]

    while word and not word[-1].isalnum():
        suffix = word[-1] + suffix
        word = word[:-1]

    if not word:
        return prefix + suffix

    original = word
    lower_word = word.lower()

    if lower_word in CUSTOM_ENGLISH_TERMS:
        corrected = lower_word
    elif lower_word in ENGLISH_CORRECTIONS:
        corrected = ENGLISH_CORRECTIONS[lower_word]
    else:
        suggestions = sym_spell.lookup(
            lower_word,
            Verbosity.CLOSEST,
            max_edit_distance=2
        )
        corrected = suggestions[0].term if suggestions else lower_word

    if original.istitle():
        corrected = corrected.title()
    elif original.isupper():
        corrected = corrected.upper()

    return prefix + corrected + suffix


def dictionary_correct_text(text: str) -> str:
    if not isinstance(text, str):
        return text

    masked_text, placeholders = preserve_sensitive_tokens(text)

    words = masked_text.split()
    corrected_words = []

    for word in words:
        if re.search(r"[\u0D80-\u0DFF]", word):
            new_word = word

            for wrong, correct in SINHALA_CORRECTIONS.items():
                if wrong in new_word:
                    new_word = new_word.replace(wrong, correct)

            corrected_words.append(new_word)
        else:
            corrected_words.append(correct_english_token_with_symspell(word))

    corrected = " ".join(corrected_words)
    corrected = restore_sensitive_tokens(corrected, placeholders)
    return corrected


def call_ollama(prompt: str) -> str:
    url = f"{DEEPSEEK_HOST}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(
            url,
            headers=headers,
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "stream": False,
            },
            timeout=600,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.exceptions.ConnectionError as e:
        raise Exception(f"Could not connect to DeepSeek API. Error: {e}")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"DeepSeek HTTP error: {e}. Response: {response.text}")
    except requests.exceptions.Timeout:
        raise Exception("DeepSeek correction request timed out.")


def llm_refine_text(raw_text: str) -> str:
    cleaned = clean_ocr_text(raw_text)
    if not cleaned:
        return ""

    dictionary_fixed = dictionary_correct_text(cleaned)
    masked, placeholders = preserve_sensitive_tokens(dictionary_fixed)

    prompt = f"""
You are correcting OCR text from a financial document.

STRICT RULES:
- Correct OCR spelling mistakes only
- Preserve all numbers, prices, totals, dates, times, phone numbers, IDs, and order numbers exactly
- Preserve Sinhala text in Sinhala script
- Do NOT translate Sinhala to English
- Do NOT transliterate Sinhala into English letters
- Do NOT rewrite the document
- Do NOT add notes, explanations, or extra words
- Do NOT merge separate lines into one paragraph
- Keep the same line order
- Keep the same line breaks as much as possible
- If unsure, keep the original word unchanged
- Return ONLY corrected OCR text

OCR text:
{masked}
""".strip()

    corrected = call_ollama(prompt)
    corrected = strip_llm_boilerplate(corrected)
    corrected = restore_sensitive_tokens(corrected, placeholders)

    if not corrected.strip():
        return dictionary_fixed

    if looks_like_bad_rewrite(dictionary_fixed, corrected):
        return dictionary_fixed

    if looks_like_transliterated_sinhala(dictionary_fixed, corrected):
        return dictionary_fixed

    return corrected