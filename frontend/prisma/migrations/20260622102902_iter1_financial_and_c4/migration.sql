-- AlterTable
ALTER TABLE "User" ADD COLUMN     "profileImage" TEXT;

-- CreateTable
CREATE TABLE "query_history" (
    "id" UUID NOT NULL,
    "user_id" TEXT NOT NULL,
    "company_name" TEXT,
    "question" TEXT NOT NULL,
    "answer" TEXT,
    "explanation" TEXT,
    "metrics" JSONB,
    "evidence" JSONB,
    "source_file" TEXT,
    "created_at" TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "query_history_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "FinancialDocument" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "documentId" TEXT NOT NULL,
    "documentType" TEXT,
    "orderId" TEXT,
    "flowType" TEXT,
    "effectiveFlowType" TEXT,
    "companyName" TEXT,
    "supplierName" TEXT,
    "docDate" TIMESTAMP(3),
    "rawTotalAmount" DECIMAL(14,2),
    "finalTotalAmount" DECIMAL(14,2),
    "totalStatus" TEXT,
    "payableAmount" DECIMAL(14,2),
    "cashReturn" DECIMAL(14,2),
    "currency" TEXT DEFAULT 'LKR',
    "receivedStatus" TEXT,
    "paidStatus" TEXT,
    "status" TEXT,
    "language" TEXT,
    "rawText" TEXT,
    "correctedText" TEXT,
    "structuredJson" JSONB,
    "correctionJson" JSONB,
    "arithmeticStatus" TEXT,
    "arithmeticJson" JSONB,
    "ocrSelectedVersion" TEXT,
    "deletedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "FinancialDocument_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "LineItem" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "documentRef" TEXT NOT NULL,
    "lineNo" INTEGER NOT NULL,
    "description" TEXT,
    "qty" DECIMAL(14,3),
    "unitPrice" DECIMAL(14,2),
    "total" DECIMAL(14,2),
    "tax" DECIMAL(14,2),
    "discount" DECIMAL(14,2),
    "currency" TEXT,
    "rawJson" JSONB,

    CONSTRAINT "LineItem_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Entity" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "entityType" TEXT NOT NULL,
    "canonicalName" TEXT NOT NULL,
    "rawName" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Entity_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "EntityAlias" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "entityRef" TEXT NOT NULL,
    "aliasText" TEXT NOT NULL,
    "score" DOUBLE PRECISION,
    "method" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "EntityAlias_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "DocLink" (
    "id" TEXT NOT NULL,
    "tenantId" TEXT NOT NULL,
    "fromDocId" TEXT NOT NULL,
    "linkType" TEXT NOT NULL,
    "toEntityRef" TEXT,
    "toDocId" TEXT,
    "confidence" DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    "evidence" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "DocLink_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "FinancialDocument_tenantId_idx" ON "FinancialDocument"("tenantId");

-- CreateIndex
CREATE INDEX "FinancialDocument_tenantId_docDate_idx" ON "FinancialDocument"("tenantId", "docDate");

-- CreateIndex
CREATE INDEX "FinancialDocument_tenantId_supplierName_idx" ON "FinancialDocument"("tenantId", "supplierName");

-- CreateIndex
CREATE UNIQUE INDEX "FinancialDocument_tenantId_documentId_key" ON "FinancialDocument"("tenantId", "documentId");

-- CreateIndex
CREATE INDEX "LineItem_tenantId_idx" ON "LineItem"("tenantId");

-- CreateIndex
CREATE INDEX "LineItem_documentRef_idx" ON "LineItem"("documentRef");

-- CreateIndex
CREATE INDEX "Entity_tenantId_entityType_idx" ON "Entity"("tenantId", "entityType");

-- CreateIndex
CREATE UNIQUE INDEX "Entity_tenantId_entityType_canonicalName_key" ON "Entity"("tenantId", "entityType", "canonicalName");

-- CreateIndex
CREATE INDEX "EntityAlias_tenantId_entityRef_idx" ON "EntityAlias"("tenantId", "entityRef");

-- CreateIndex
CREATE INDEX "EntityAlias_tenantId_aliasText_idx" ON "EntityAlias"("tenantId", "aliasText");

-- CreateIndex
CREATE INDEX "DocLink_tenantId_fromDocId_idx" ON "DocLink"("tenantId", "fromDocId");

-- CreateIndex
CREATE INDEX "DocLink_tenantId_toDocId_idx" ON "DocLink"("tenantId", "toDocId");

-- CreateIndex
CREATE INDEX "DocLink_tenantId_linkType_idx" ON "DocLink"("tenantId", "linkType");

-- AddForeignKey
ALTER TABLE "LineItem" ADD CONSTRAINT "LineItem_documentRef_fkey" FOREIGN KEY ("documentRef") REFERENCES "FinancialDocument"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "EntityAlias" ADD CONSTRAINT "EntityAlias_entityRef_fkey" FOREIGN KEY ("entityRef") REFERENCES "Entity"("id") ON DELETE CASCADE ON UPDATE CASCADE;
