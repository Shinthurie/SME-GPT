import os
import json
import requests

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_HOST = "https://api.deepseek.com"


def call_ollama(prompt: str) -> str:
    url = f"{DEEPSEEK_HOST}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
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


def detect_currency(result: dict) -> str:
    evidence = result.get("evidence", []) or []

    for item in evidence:
        currency = str(item.get("currency", "")).strip().upper()
        if currency in ["LKR", "RS", "RS.", "RS"]:
            return "LKR"

    return "LKR"


def format_money(amount: float, currency: str) -> str:
    if currency.upper() == "LKR":
        return f"LKR {amount:,.2f}"
    return f"{currency} {amount:,.2f}"


def build_fallback_answer(question: str, company_name: str, result: dict) -> tuple[str, str]:
    if not result.get("success"):
        explanation = result.get("explanation", "No answer could be generated.")
        return explanation, explanation

    qtype = result.get("question_type", "summary")
    metrics = result.get("metrics", {})
    evidence = result.get("evidence", [])
    currency = detect_currency(result)

    if qtype == "receivable":
        total = metrics.get("total_receivable_amount", 0.0)
        doc_count = metrics.get("receivable_documents", 0)

        short_answer = f"The current receivable amount for {company_name} is {format_money(total, currency)}."

        full_answer = (
            f"Based on the analysis result provided, which is based only on financial_documents_clean.csv, "
            f"we found {doc_count} receivable document(s) for company '{company_name}'. "
            f"The receivable amount is aggregated to {format_money(total, currency)}. "
            f"These documents were included because they matched the current user, matched the company name, "
            f"and matched the effective flow type of 'receivable'."
        )
        return short_answer, full_answer

    if qtype == "payable":
        total = metrics.get("total_payable_amount", 0.0)
        doc_count = metrics.get("payable_documents", 0)

        short_answer = f"The current payable amount for {company_name} is {format_money(total, currency)}."

        full_answer = (
            f"Based on the analysis result provided, which is based only on financial_documents_clean.csv, "
            f"we found {doc_count} payable document(s) for company '{company_name}'. "
            f"The payable amount is aggregated to {format_money(total, currency)}. "
            f"These documents were included because they matched the current user, matched the company name, "
            f"and matched the effective flow type of 'payable'."
        )
        return short_answer, full_answer

    if qtype in ["invoice_list", "receipt_list", "po_list", "dn_list"]:
        doc_count = len(evidence)
        short_answer = f"I found {doc_count} matching document(s) for {company_name}."

        full_answer = (
            f"Based on the analysis result provided, which is based only on financial_documents_clean.csv, "
            f"I found {doc_count} matching document(s) for company '{company_name}'. "
            f"The returned evidence was filtered using the current user context and matching document type."
        )
        return short_answer, full_answer

    short_answer = f"I found {len(evidence)} matching record(s) for {company_name}."

    full_answer = (
        f"Based on the analysis result provided, which is based only on financial_documents_clean.csv, "
        f"I found {len(evidence)} matching record(s) for company '{company_name}'. "
        f"The result was generated using only the current user's saved records."
    )
    return short_answer, full_answer


def generate_explainable_answer(question: str, company_name: str, result: dict) -> dict:
    if not result.get("success"):
        explanation = result.get("explanation", "No answer available.")
        return {
            "short_answer": explanation,
            "full_answer": explanation,
        }

    prompt = f"""
You are a financial assistant.

Rules:
- Use ONLY the provided analysis result
- Do NOT invent numbers
- Do NOT invent document IDs
- The direct answer must be SHORT and business-friendly
- The explanation must be separate and concise
- If currency is LKR, use LKR in the answer
- If a total is aggregated, clearly say it is aggregated
- Mention that evidence comes only from financial_documents_clean.csv
- Do not mention hidden reasoning

Return ONLY valid JSON in this exact shape:
{{
  "short_answer": "",
  "full_answer": ""
}}

Company Context:
{company_name}

User Question:
{question}

Analysis Result:
{json.dumps(result, ensure_ascii=False, indent=2)}
""".strip()

    try:
        response = call_ollama(prompt)
        start = response.find("{")
        end = response.rfind("}")

        if start != -1 and end != -1 and end > start:
            parsed = json.loads(response[start:end + 1])
            short_answer = str(parsed.get("short_answer", "")).strip()
            full_answer = str(parsed.get("full_answer", "")).strip()

            if short_answer and full_answer:
                return {
                    "short_answer": short_answer,
                    "full_answer": full_answer,
                }
    except Exception:
        pass

    short_answer, full_answer = build_fallback_answer(question, company_name, result)
    return {
        "short_answer": short_answer,
        "full_answer": full_answer,
    }