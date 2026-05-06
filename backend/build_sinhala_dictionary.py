from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Iterable


SINHALA_CHAR_PATTERN = re.compile(r"[\u0D80-\u0DFF]")
ONLY_SINHALA_WORD_PATTERN = re.compile(r"^[\u0D80-\u0DFF\u200d\u200c]+$")

# Add your project-specific must-keep terms here.
PRIORITY_TERMS = {
    "ඉන්වොයිස්",
    "බිල්පත",
    "මුළු",
    "එකතුව",
    "වට්ටම",
    "ගෙවීම",
    "ගෙවිය යුතු",
    "ලැබිය යුතු",
    "සැපයුම්කරු",
    "ඇණවුම",
    "ප්‍රමාණය",
    "මුදල්",
    "වටිනාකම",
    "දිනය",
    "මුදල",
    "ශේෂය",
    "ගාස්තුව",
    "වෙළඳසල",
    "සේවාව",
    "අයිතමය",
    "ගනුදෙනුව",
    "ගෙවීම්",
    "ලැබීම්",
    "ආදායම",
    "වියදම",
    "මුළු එකතුව",
    "වට්ටම්",
    "බැංකුව",
    "පාරිභෝගිකයා",
    "සමාගම",
}


def clean_word(word: str) -> str:
    word = word.strip()
    word = word.replace("\ufeff", "")
    word = word.replace("\u200b", "")
    word = word.replace("\u2060", "")
    word = word.replace("\xa0", " ")
    word = re.sub(r"\s+", " ", word).strip()

    # Remove numbering / bullets around words
    word = re.sub(r"^[\-\*\.\,\:\;\"\'\(\)\[\]\{\}0-9]+", "", word)
    word = re.sub(r"[\-\*\.\,\:\;\"\'\(\)\[\]\{\}0-9]+$", "", word)

    return word.strip()


def is_valid_sinhala_word(word: str) -> bool:
    if not word:
        return False

    if not SINHALA_CHAR_PATTERN.search(word):
        return False

    # Allow multi-word Sinhala phrases like "ගෙවිය යුතු"
    parts = word.split()
    if not parts:
        return False

    return all(ONLY_SINHALA_WORD_PATTERN.fullmatch(part) for part in parts)


def iter_input_lines(paths: Iterable[Path]) -> Iterable[str]:
    for path in paths:
        if not path.exists():
            print(f"[WARN] Missing file: {path}")
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                yield line.rstrip("\n")


def extract_candidate_words(lines: Iterable[str]) -> list[str]:
    candidates: list[str] = []

    for line in lines:
        raw = line.strip()
        if not raw:
            continue

        # Split TSV/CSV-ish lines and keep first Sinhala-looking field
        parts = re.split(r"[\t,|]", raw)
        chosen = None

        for part in parts:
            cleaned = clean_word(part)
            if is_valid_sinhala_word(cleaned):
                chosen = cleaned
                break

        if chosen is None:
            cleaned = clean_word(raw)
            if is_valid_sinhala_word(cleaned):
                chosen = cleaned

        if chosen:
            candidates.append(chosen)

    return candidates


def score_words(words: list[str]) -> list[str]:
    """
    If the source is frequency-ordered, this preserves useful order.
    If not, duplicates naturally boost repeated useful words.
    """
    counts = Counter(words)

    # Keep priority terms first if present or if you want them forced in.
    ordered: list[str] = []
    seen = set()

    for term in sorted(PRIORITY_TERMS):
        if term not in seen:
            ordered.append(term)
            seen.add(term)

    # Then sort remaining words by frequency desc, then shorter/common-looking terms first.
    remaining = sorted(
        (w for w in counts if w not in seen),
        key=lambda w: (-counts[w], len(w), w),
    )

    ordered.extend(remaining)
    return ordered


def write_output(words: list[str], output_path: Path, limit: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    selected = words[:limit]

    with open(output_path, "w", encoding="utf-8") as f:
        for word in selected:
            f.write(word + "\n")

    print(f"[OK] Wrote {len(selected)} words to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a clean Sinhala dictionary file for OCR correction."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="One or more source text files containing Sinhala words or frequency lists.",
    )
    parser.add_argument(
        "--output",
        default="backend/dictionaries/sinhala_common_5000.txt",
        help="Output dictionary path.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Number of words to keep in output.",
    )

    args = parser.parse_args()

    input_paths = [Path(p) for p in args.inputs]
    output_path = Path(args.output)

    lines = iter_input_lines(input_paths)
    candidates = extract_candidate_words(lines)

    if not candidates:
        raise ValueError("No valid Sinhala words found in the provided input files.")

    ordered_words = score_words(candidates)
    write_output(ordered_words, output_path, args.limit)


if __name__ == "__main__":
    main()