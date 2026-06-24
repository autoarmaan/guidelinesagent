# Knowledge Center Migration — Decision & Implementation

## Decision (2026-06-23)

**Problem:** The original AI Studio migration plan required a Qdrant vector store connection, but no working Qdrant URL was available (Blocker #1 in AI_STUDIO_ERRORS_AND_STATUS.md).

**Solution:** Use **Knowledge Center (KC)** with `knowledge_retrieval` instead of direct Qdrant `vector_store`. KC manages its own vector storage internally — no external Qdrant connection needed.

**Who decided:** Mentor recommended Knowledge Retrieval approach.

---

## Architecture Change

### Before (Local)
```
documents/*.docx → document_loader.py (parse sections)
  → vector_store.py (OpenAI embeddings → local ChromaDB)
  → main.py (query ChromaDB → GPT-4o-mini → citations)
  → React frontend
```

### After (AI Studio)
```
PDFs in Azure Blob (anwuat3024/guideline-documents)
  → KC Dataset "compliance-guidelines" (auto: OCR → chunk → embed → managed vector store)
  → Chatbot workflow agent with knowledge_retrieval tool
  → AI Studio API (can be called from frontend)
```

---

## What Was Done

### 1. Created KC Dataset via API
- **Name:** `compliance-guidelines`
- **ID:** `45e640ac-6d10-454f-8289-8d43d9904dab`
- **Created via:** `POST /kc/api/v1/datasets`

### 2. Connected Azure Blob Data Source
- **Connection:** `guideline-documents-blob` (ID: `218ed6b3-d8d0-41e0-8452-c954fb4ce9c4`)
- **Container:** `anwuat3024/guideline-documents`
- **Import Path:** `/`

### 3. Uploaded Documents (as PDF — KC only supports PDF)
- `Autonomize – Data Retention, Archival, And Purge Policy.pdf` (converted from .docx)
- `questionnaire-v3-AI.pdf` (converted from .docx)
- Uploaded manually to Azure Blob portal, then synced in KC UI

### 4. Processing
- Click "Process All" in KC UI to trigger ingestion pipelines
- KC handles: OCR (Azure Doc Intelligence) → text chunking → embedding → vector storage

---

## Next Steps

### Step 1: Build Chatbot Agent Workflow
Create a workflow with an LLM agent that uses `knowledge_retrieval` to search the `compliance-guidelines` dataset.

Key config:
```yaml
tools:
  - name: Knowledge Retrieval
    type: component
    config:
      limit: 10
      knowledge_name: compliance_guidelines  # KC dataset unique_name
      component: knowledge_retrieval
```

System prompt: compliance/security policy expert with citation rules.

### Step 2: Test via CLI
```bash
autonomize run <workflow-id> --input message="What is our data retention policy?"
```

### Step 3: Connect Frontend to AI Studio API
Replace the local FastAPI backend (`main.py` → direct OpenAI + ChromaDB) with calls to the AI Studio workflow execution API. The React frontend stays the same — just the backend changes from local to cloud.

---

## Key Learnings

1. **KC only supports PDF** — `.docx` files must be converted before upload
2. **KC dataset creation works via API** (`POST /kc/api/v1/datasets`) but document upload/ingestion is UI-only (authz not configured on gateway for `/kc/api/v1/documents/upload`)
3. **`knowledge_retrieval`** is a built-in component tool — no connection setup needed, it queries KC's managed vector store directly
4. **KC API base path:** `https://genesis.integration.autonomize.ai/kc/api/v1/`
5. **Blob upload flow:** Upload PDFs to Azure Blob → Connect as data source in KC → Sync → Process All

## Current Blocker: Qdrant Disk Space (2026-06-23)

### Error
The "Standard Document Ingestion" pipeline (v3.0.1) was linked and "Process All" was clicked. OCR and chunking succeeded, but the final `store_vectors` step failed:

```
Step store_vectors failed: RuntimeError: connector tool 'upsert_documents' failed
[UnexpectedResponse]: Unexpected Response: 500 (Internal Server Error)
Raw response: {"status":{"error":"Service internal error: No space left on device:
WAL buffer size exceeds available disk space"},"time":0.000568756}
```

### Root Cause
The **platform-managed Qdrant instance** used internally by Knowledge Center has run out of disk space. This is the same underlying Qdrant infrastructure issue from the original migration attempt (Blocker #1 in `AI_STUDIO_ERRORS_AND_STATUS.md`), just surfaced through KC instead of a direct connection.

- **Document ID:** `3ac252a7-e9cc-41d9-a219-fbfc875db163`
- **Failed execution:** `d3c943e0-d331-4e7c-9dd0-962595a718d3`
- **Pipeline that failed:** `4a73f5d4-3b4a-4854-8ef3-29f7953bd432` (Standard Document Ingestion)
- **Step that failed:** `store_vectors` → `upsert_documents` tool on internal `knowledge_center_vector_store` connection

### What Succeeded
- Document upload to Azure Blob ✓
- Sync to KC dataset ✓
- Pipeline link (Standard Document Ingestion v3.0.1) ✓
- OCR (Azure Doc Intelligence) ✓
- Text chunking ✓
- Embedding generation ✓
- **Vector storage → FAILED (Qdrant disk full)**

### Impact
Knowledge Center uses Qdrant internally for its managed vector store. Until the platform team frees disk space or provisions a larger Qdrant volume, no KC dataset can store new vectors in the integration environment.

### Resolution: Use Metadata-Enriched Document Ingestion Pipeline
Linked all three system pipelines and clicked "Process All":
- **Standard Document Ingestion** → Error (Qdrant disk full)
- **Scanned Document Ingestion** → Error (Qdrant disk full)
- **Metadata-Enriched Document Ingestion** → **Processed ✓**

The Metadata-Enriched pipeline uses a **different vector backend** (likely Azure AI Search instead of Qdrant), which bypasses the Qdrant disk space issue entirely. This is the pipeline to use going forward.

### Remaining Qdrant Issue (Low Priority)
The other two pipelines still fail due to Qdrant disk space. Not a blocker since Metadata-Enriched works. Platform team may want to clean up the 556 datasets (mostly empty `sdk-test-*` leftovers) or expand Qdrant storage eventually.

---

## AI Studio Assets

| Asset | Type | ID | Status |
|-------|------|----|--------|
| compliance-guidelines | KC Dataset | 45e640ac-6d10-454f-8289-8d43d9904dab | Active, 1 doc processed (Metadata-Enriched pipeline) |
| Compliance Guidelines Chatbot | Workflow | f21caa65-d208-4de7-a257-1ab9167c8c98 | Created, waiting on vector store |
| guideline-documents-blob | Azure Blob Connection | 218ed6b3-d8d0-41e0-8452-c954fb4ce9c4 | Connected/Healthy |
| guideline-documents | Azure Blob Container | anwuat3024 | Has PDF docs |
| Upload PDF to Blob | Workflow (utility) | d7df72ba-637d-4327-a9e4-4b35c9c18659 | Created (unused) |
