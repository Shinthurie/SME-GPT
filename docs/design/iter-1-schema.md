# Iteration 1 — Database Schema Design

> Status: **proposal for review** (issue #5). Implements ROADMAP Iteration 1.
> Owner: Shinthurie (DB) · Ashfak helps on C4 tables. Review before we touch `schema.prisma`.

## Goal

Replace the CSV store (`backend/financial_documents_clean.csv` via `dataset_manager.py`) with a
real, tenant-isolated PostgreSQL schema on **Supabase**. Add the C4 relationship tables now (used in
Iteration 6) so we migrate the data once.

---

## Decisions

### 1. Single schema source of truth = **Prisma**
`frontend/prisma/schema.prisma` already defines `User`, `query_history`, etc. We keep **Prisma as
the only migration tool**. The backend does **not** run its own migrations; it reads/writes the same
tables via **psycopg (raw SQL)**. This avoids two migration systems fighting over one database.

- Shinthurie: owns `schema.prisma` + `prisma migrate`.
- Ashfak: backend psycopg data-access layer against those tables.

### 2. `tenant_id` = `User.id` (string), not UUID
The research C4 schema uses `UUID`. Our existing `User.id` is a **cuid string** (`@default(cuid())`).
To stay consistent with the live auth system, **`tenant_id` is a `String` foreign key to `User.id`**
on every table. (We note the deviation from the research's UUID; it does not change any logic.)

### 3. pgvector deferred to Iteration 4
The `vector` extension is enabled now, but the embeddings table is added in Iteration 4 (RAG), not
here. This doc only covers relational tables.

### 4. Money as `Decimal`, not float
All amounts use `Decimal(14,2)` to avoid float rounding in financial data.

---

## Proposed models (Prisma)

```prisma
model FinancialDocument {
  id                  String   @id @default(cuid())
  tenantId            String                    // = User.id
  documentId          String                    // business id (existing "document_id")
  documentType        String?                   // invoice | purchase_order | receipt | delivery_note
  orderId             String?                   // PO / order reference
  flowType            String?                   // payable | receivable | paid | received
  effectiveFlowType   String?                   // derived: income | expense
  companyName         String?                   // buyer / your company
  supplierName        String?                   // vendor
  docDate             DateTime?                 // existing "date"
  rawTotalAmount      Decimal? @db.Decimal(14,2)
  finalTotalAmount    Decimal? @db.Decimal(14,2)
  totalStatus         String?
  payableAmount       Decimal? @db.Decimal(14,2)
  cashReturn          Decimal? @db.Decimal(14,2)
  currency            String?  @default("LKR")
  receivedStatus      String?
  paidStatus          String?
  status              String?
  language            String?                   // en | si
  rawText             String?  @db.Text
  correctedText       String?  @db.Text
  structuredJson      Json?
  correctionJson      Json?
  arithmeticStatus    String?
  arithmeticJson      Json?
  ocrSelectedVersion  String?
  createdAt           DateTime @default(now())
  updatedAt           DateTime @updatedAt
  lineItems           LineItem[]

  @@unique([tenantId, documentId])
  @@index([tenantId])
  @@index([tenantId, docDate])
  @@index([tenantId, supplierName])
}

model LineItem {
  id           String   @id @default(cuid())
  tenantId     String
  documentRef  String                          // FK -> FinancialDocument.id
  lineNo       Int
  description  String?                          // canonical: description / item
  qty          Decimal? @db.Decimal(14,3)
  unitPrice    Decimal? @db.Decimal(14,2)
  total        Decimal? @db.Decimal(14,2)
  tax          Decimal? @db.Decimal(14,2)
  discount     Decimal? @db.Decimal(14,2)
  currency     String?
  rawJson      Json?                            // original parsed item, for audit
  document     FinancialDocument @relation(fields: [documentRef], references: [id], onDelete: Cascade)

  @@index([tenantId])
  @@index([documentRef])
}

// ---- Component 4 tables (created now, populated in Iteration 6) ----

model Entity {
  id            String   @id @default(cuid())
  tenantId      String
  entityType    String                          // vendor | doc_ref | item | category
  canonicalName String
  rawName       String?
  createdAt     DateTime @default(now())
  aliases       EntityAlias[]

  @@unique([tenantId, entityType, canonicalName])
  @@index([tenantId, entityType])
}

model EntityAlias {
  id        String   @id @default(cuid())
  tenantId  String
  entityRef String
  aliasText String
  score     Float?
  method    String                              // normalize | fuzzy | manual
  createdAt DateTime @default(now())
  entity    Entity   @relation(fields: [entityRef], references: [id], onDelete: Cascade)

  @@index([tenantId, entityRef])
  @@index([tenantId, aliasText])
}

model DocLink {
  id          String   @id @default(cuid())
  tenantId    String
  fromDocId   String
  linkType    String                            // HAS_VENDOR | REFERENCES | CONTAINS_ITEM | HAS_REF
  toEntityRef String?
  toDocId     String?
  confidence  Float    @default(1.0)
  evidence    Json?                             // {page, bbox, chunk_id, extracted_text, rule}
  createdAt   DateTime @default(now())

  @@index([tenantId, fromDocId])
  @@index([tenantId, toDocId])
  @@index([tenantId, linkType])
}
```

`query_history` already exists in `schema.prisma` (keep as-is; it already has `user_id` = tenant).
`OcrBox`/provenance table is **not** added here — it belongs with Component 2 (Iteration 3), where
the box/chunk schema is finalized.

---

## CSV → `FinancialDocument` column mapping

| CSV column | New field | Notes |
|---|---|---|
| `user_id` | `tenantId` | = User.id |
| `document_id` | `documentId` | unique per tenant |
| `document_type` | `documentType` | |
| `order_id` | `orderId` | |
| `flow_type` | `flowType` | |
| `effective_flow_type` | `effectiveFlowType` | derived income/expense |
| `company_name` | `companyName` | |
| `supplier_name` | `supplierName` | |
| `date` | `docDate` | parse to DateTime |
| `raw_total_amount` | `rawTotalAmount` | → Decimal |
| `final_total_amount` | `finalTotalAmount` | → Decimal |
| `total_status` | `totalStatus` | |
| `payable_amount` | `payableAmount` | → Decimal |
| `cash_return` | `cashReturn` | → Decimal |
| `currency` | `currency` | |
| `received_status` | `receivedStatus` | |
| `paid_status` | `paidStatus` | |
| `status` | `status` | |
| `language` | `language` | |
| `raw_text` | `rawText` | |
| `corrected_text` | `correctedText` | |
| `items_json` | → `LineItem[]` | normalized into rows (keep raw in `LineItem.rawJson`) |
| `structured_json` | `structuredJson` | Json |
| `correction_json` | `correctionJson` | Json |
| `arithmetic_status` | `arithmeticStatus` | |
| `arithmetic_json` | `arithmeticJson` | Json |
| `ocr_selected_version` | `ocrSelectedVersion` | |

---

## Tenant isolation rule

Every backend query **must** filter by `tenantId`. The data-access layer takes `tenant_id` as a
required argument; no query runs without it. Tested in issue #8 (user A cannot read user B's rows).

## Migration (issue #7)

1. Read `financial_documents_clean.csv`.
2. For each row: upsert `FinancialDocument` (key = `tenantId` + `documentId`), parse `items_json`
   into `LineItem` rows.
3. `tenantId` = the row's `user_id`.
4. Dry-run mode prints planned inserts + counts; real run is idempotent (re-runnable).
5. Verify: row counts match; spot-check totals.

## Open questions for review
1. Confirm `tenant_id` as String (cuid) vs migrating to UUID. Recommendation: **String** (matches auth).
2. Keep both normalized `LineItem` rows **and** raw `items_json`? Recommendation: **yes** (audit safety) — `rawJson` holds the original.
3. Do we want soft-delete (`deletedAt`) on `FinancialDocument` for the "confirm before delete" safety requirement (SRS §5.2)? Recommendation: add `deletedAt DateTime?` — cheap now.
