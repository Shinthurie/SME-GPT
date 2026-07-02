# SME-GPT — Production Readiness Assessment

> Prepared for the industry-professional review. Honest, evidence-based verdict — written so you can defend every claim.

## TL;DR verdict

**SME-GPT is a feature-complete, well-architected late-stage MVP that is _pilot/beta-ready_ — not yet _hardened enterprise production_.**

You can confidently demo it, onboard a handful of real Sri Lankan SMEs in a controlled pilot, and show a credible path to full production. Be upfront that a few operational hardening items (hosted OCR, at-rest encryption, monitoring/SLA) remain before an unattended public launch. Presenting it this way is a *strength* — it shows engineering maturity, not weakness.

**One-line framing for the panel:** *"The product and the AI pipeline are done and tested end-to-end; what's left is operational hardening — the same last-mile every real product goes through before GA."*

---

## What IS production-grade today (with evidence)

| Area | Status | Evidence |
|---|---|---|
| **End-to-end pipeline** | ✅ Live | Upload → OCR → correction → extraction → validation → save → query, all wired and used by the UI |
| **Neuro-symbolic Q&A (the research contribution)** | ✅ Live | PAL: Planner→Validator→Executor→Answer on `/ask-query`; LLM never does arithmetic |
| **Multi-tenancy & isolation** | ✅ | Every read/write filters `tenantId = user_id`; enforced in scope resolver, data tools, every `load_records` |
| **AuthN/AuthZ** | ✅ | JWT + bcrypt, optional 2FA, device trust, RBAC (admin/write/auditor), session-version invalidation on password reset |
| **Database** | ✅ | Postgres (Supabase) + `pgvector`; connection pooling; stale-connection retry + TCP keepalives (recent hardening) |
| **Resilience** | ✅ | OCR colab→local fallback; PAL→legacy fallback; DB retry; background post-save so the UI never blocks/times out |
| **Deploy artifacts** | ✅ | `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `nginx/` (TLS certs + reverse proxy), `render.yaml`, `.env.example` |
| **CI** | ✅ | `.github/workflows/ci.yml` |
| **Automated tests** | ✅ | 25 test files in `backend/tests/`, ~309 passing (security, GDPR, financial logic, pipeline, PAL) |
| **Bilingual (Sinhala/English)** | ✅ | Detection, query normalization, LLM masking, bilingual UI |
| **GDPR-style data rights** | ✅ | `GET /user/export`, `DELETE /user/account` hard-delete every tenant-scoped table |
| **Standardised errors & status** | ✅ | Uniform `{success:false, error_code, message}`; SSE live progress on upload |

## What is NOT yet production-hardened (be honest about these)

| Gap | Risk | Why it's acceptable *for a pilot* | Path to production |
|---|---|---|---|
| **OCR runs on a Colab notebook + ngrok tunnel** | 🔴 High — single point of failure, not always-on, tunnel URL changes | Fine for demo/pilot; the OCR layer is *pluggable* behind an interface | Deploy Surya on a managed GPU (Modal, RunPod, HF Inference, or a small always-on GPU VM); swap the URL — no pipeline change |
| **LLM inference via cloud APIs (Gemini/DeepSeek)** | 🟠 Medium — financial data leaves the device | Acceptable with consent; keys are env-gated; Ollama local fallback exists | Offer on-prem/local (Ollama/fine-tuned model) tier for sensitive tenants; sign DPAs |
| **At-rest app-layer encryption (SRS NFR-31)** | 🟠 Medium | Supabase encrypts at rest at the disk level; saved images are on an (assumed) encrypted volume | Add app-layer AES-256 for document blobs + column encryption for PII |
| **Monitoring / SLA / 99% uptime (NFR-05)** | 🟠 Medium | Not needed to prove the concept | Add health checks, uptime monitoring (e.g. Better Uptime), error tracking (Sentry), alerting |
| **Audit-log 1-year retention policy (NFR-15)** | 🟡 Low | Logs are written; retention just isn't scheduled | Add a scheduled purge/retention job |
| **In-memory session state between `/process-document` and `/confirm-save`** | 🟡 Low | Lost on restart; acceptable at pilot scale | Move to Redis/DB if horizontally scaling |
| **Load / scale testing** | 🟡 Low | Single-tenant volumes are small | Run load tests before multi-org GA |

---

## Readiness scorecard (by dimension)

| Dimension | Score | Notes |
|---|---|---|
| Functional completeness | 9/10 | Core + many extras (reports, bulk upload, analytics, manual entry) shipped |
| Architecture & code quality | 9/10 | Clean separation, pluggable interfaces, strong invariants, tested |
| AI/ML correctness & safety | 9/10 | Deterministic arithmetic (PAL), validator allow-list, no LLM math |
| Security (app layer) | 8/10 | Strong auth/RBAC/tenancy; at-rest encryption pending |
| Reliability of dependencies | 5/10 | OCR-on-Colab is the weak link |
| Ops/observability | 4/10 | Docker/CI yes; monitoring/alerting/SLA no |
| **Overall** | **~7.5/10 — Pilot-ready** | Clear, short path to GA |

---

## The 5 things to do before a real production launch (priority order)

1. **Host the OCR service on an always-on GPU** (kills the biggest risk).
2. **Add observability**: Sentry (errors) + uptime monitor + `/health` dashboards.
3. **At-rest encryption** for document images + PII columns; document the key management.
4. **Offer a data-privacy tier** (local LLM/on-prem) for tenants who can't send data to cloud APIs.
5. **Load test** the upload + query paths at 10–50× current volume; add Redis for session state if scaling out.

Everything above is *operational*, not architectural — the design already anticipates each (pluggable OCR, LLM abstraction, tenant_id everywhere). That's the key message.
