# AI Studio Migration — Errors, Fixes, and Remaining Blockers

## Summary

We attempted to migrate the local RAG chatbot to the Autonomize AI Studio platform. Several issues were encountered and some were resolved, but two infrastructure blockers remain that prevent a full migration. The local app was improved instead.

---

## Setup (Completed Successfully)

| Step | Status | Details |
|------|--------|---------|
| Install Autonomize SDK | Done | `pip install autonomize_sdk-0.5.4-py3-none-any.whl` |
| Configure environment | Done | `autonomize env add my-env --from .env` |
| Login | Done | `autonomize login` — authenticated as armaan.amatya@autonomize.ai |
| List workflows | Done | 100 workflows, 88 templates available |
| Create Azure Blob connection | Done | `guideline-documents-blob` → anwuat3024/guideline-documents container |
| Upload guideline doc | Done | `uploads/Autonomize-Data-Retention-Archival-And-Purge-Policy.docx` |

---

## Errors Encountered and Fixed

### 1. Unicode Encoding Error on Windows (CLI output)

**Error:**
```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2713' in position 0
```

**Cause:** The Autonomize CLI uses Rich library with Unicode checkmarks (✓) that Windows cp1252 encoding can't render.

**Fix:** Prefix all CLI commands with `PYTHONIOENCODING=utf-8`.

---

### 2. Template Output Path Mismatch

**Error:**
```
Step 'download_files': input '{{steps.list_files.output.parts.0.content.files}}'
resolved to None. Available: steps.list_files.output.files
```

**Cause:** The `rag_ingestion_large_files` template references `steps.list_files.output.parts.0.content.files` but the `azure_blob` connector's `list_files` tool returns data at `steps.list_files.output.files` (no `parts.0.content` wrapper).

**Fix:** Exported workflow to YAML, replaced all `steps.list_files.output.parts.0.content.files` → `steps.list_files.output.files`, re-imported.

---

### 3. Batch/ForEach Platform Bug

**Error:**
```
Workflow execution failed: Batch item 0 failed: Activity task failed
```

**Cause:** The workflow engine's `batch` and `for_each` directives fail to resolve `batch_item` when iterating over tool results. Individual tool calls (list_files, download_file) work fine when called directly, but wrapping them in a batch/for_each loop causes a generic "Activity task failed" error.

**Tested:**
- `batch` + `for_each` together → fails
- `for_each` only (no `batch`) → fails
- Direct call with hardcoded input → works

**Fix:** Removed batch/for_each, built a single-file sequential pipeline instead. This is a **platform bug** — reported but not fixed.

---

### 4. Azure Doc Intelligence — Tool Not Found

**Error:**
```
Tool 'extract_layout_with_chunks' not found in Agent 'None' nor Global Registry
```

**Cause:** The workflow step used `connector: azure_doc_intel` without specifying a `connection_name`. All existing user-created Doc Intelligence connections appeared "disconnected" in the CLI.

**Discovery:** The API showed `My Azure Document Intelligence` (ID: `26e54191`) was actually **connected and healthy** (2171ms latency), despite the CLI showing "disconnected". This is a CLI display bug.

**Fix:** Could specify `connection_name: "My Azure Document Intelligence"` in the workflow. However, this was deprioritized because `.docx` files don't need OCR — text extraction works directly with python-docx.

---

### 5. Vector Store Component — Connection Validation Error

**Error:**
```
1 validation error for VectorStoreComponent: connection_name...
```

**Cause:** The `vector_store` component tool (used inside an LLM agent) requires an active Qdrant connection. Setting `connection_name: null` (as the templates do) doesn't auto-resolve to a working connection.

**Status:** UNRESOLVED — see Remaining Blockers below.

---

### 6. FastAPI/Starlette Version Conflict

**Error:**
```
TypeError: Router.__init__() got an unexpected keyword argument 'on_startup'
```

**Cause:** Installing the Autonomize SDK upgraded `starlette` from 0.38.6 to 1.3.1 and `pydantic` from 2.9.2 to 2.13.4, breaking compatibility with `fastapi==0.115.0`.

**Fix:** `pip install "fastapi==0.115.0" "starlette>=0.37.2,<0.39.0"` to downgrade starlette back.

---

### 7. Special Characters in Blob Names

**Error:** Workflows failed when blob names contained em dashes (–) and commas.

**Fix:** Renamed uploaded blob from `Autonomize – Data Retention, Archival, And Purge Policy.docx` to `Autonomize-Data-Retention-Archival-And-Purge-Policy.docx`.

---

## Remaining Blockers (Unresolved)

### Blocker 1: No Working Qdrant Vector Store Connection

**What:** Every Qdrant URL we tried returns "Health check returned unhealthy status."

**URLs tested:**
- `https://qdrant.sprint.autonomize.dev:443` (from existing disconnected connection)
- `https://qdrant.integration.autonomize.dev:443`
- `https://qdrant.integration.autonomize.ai:443`
- `http://qdrant:6333` (k8s internal)
- `http://qdrant.default:6333`, `http://qdrant.genesis:6333`, `http://qdrant-qdrant:6333`, `http://genesis-qdrant:6333`, `http://qdrant.platform:6333`

**Impact:** Cannot store or retrieve document embeddings via AI Studio. This blocks both the ingestion workflow and the chatbot workflow from using AI Studio's vector store.

**To resolve:** Need the platform team to provide:
1. The correct Qdrant URL for the integration environment
2. Any required API key for authentication
3. Or set up a new Qdrant instance / Azure AI Search instance

---

### Blocker 2: Azure Doc Intelligence Key Access

**What:** The user's Azure role (`AutoForge Developer`) doesn't have permission to view Cognitive Services keys.

**Error:** "You are not authorized to view the keys. Contact the subscription owner for assistance."

**Resource:** `anw-uat-3024-fr` at `https://anw-uat-3024.cognitiveservices.azure.com/`

**Impact:** Cannot create a new Doc Intelligence connection with API key auth. However, an existing connection (`26e54191` — "My Azure Document Intelligence") IS working and healthy, so this is a **workaround-able** issue.

**To resolve:** Either:
- Use the existing working connection (`26e54191`) — just reference it by name in workflows
- Get `Cognitive Services Contributor` role assigned to create new connections

---

## What Was Done Instead (Local App Improvements)

Since AI Studio migration is blocked by the vector store issue, we improved the local app:

### 1. Section-Aware Parser Wired Up
- **Before:** Naive 500-word chunking, no section awareness
- **After:** `extract_sections_from_docx` — detects headings, builds hierarchical paths like `Data Retention Policy > 5.1 Retention Timeframes`, converts tables to markdown
- **File:** `backend/vector_store.py` — changed `load_documents` → `extract_sections_from_docx`

### 2. Structured Source Citations
- **Before:** Raw text blobs with no indication of which document or section
- **After:** Each source shows document name + section path (e.g., "Autonomize Data Retention Policy — 5.1 Retention Timeframes (Default)")
- **Files:** `backend/vector_store.py` (returns metadata), `backend/main.py` (structured SourceChunk response), `frontend/src/components/ChatBot.jsx` (renders source header + text)

### 3. Conversation Memory
- **Before:** Every question was independent, no follow-up support
- **After:** 10-turn conversation buffer per session. Follow-up questions like "tell me more about that" now work
- **Files:** `backend/main.py` (session history dict), `frontend/src/components/ChatBot.jsx` (generates session_id per page load)

---

## AI Studio Assets Created

These workflows/connections exist in AI Studio and can be reused once blockers are resolved:

| Asset | Type | ID | Status |
|-------|------|----|--------|
| guideline-documents-blob | Azure Blob Connection | 218ed6b3-d8d0-41e0-8452-c954fb4ce9c4 | Healthy |
| Guidelines RAG Ingestion | Workflow | 8ea86927-1a1c-4920-a24c-d731ca7d7761 | Fixed (needs vector store) |
| Guideline Ingestion Agent | Workflow | 50a5afd5-0586-469f-96ed-0756fbad98ba | Needs vector store connection |
| Embed and Store Chunks | Workflow | a8f5f8b1-5949-4218-acb3-4c01eca05263 | Needs vector store connection |
| guideline-documents container | Azure Blob Storage | anwuat3024/guideline-documents | Has uploaded doc |

---

## Next Steps

1. **Get Qdrant URL from platform team** → unblocks full AI Studio migration
2. **Once vector store works:** create the Detailed Summary Agent chatbot workflow with citations enabled
3. **Create Azure Blob connection in AI Studio for Doc Intel** using existing working connection (`26e54191`)
4. **Clean up test workflows** — delete Test List Files, Test Download File, Test Batch Download, Simple Guideline Ingestion
