# Document Ingestion & OCR Processing v2

## Overview

This AI Studio graph workflow ingests documents via Azure Document Intelligence, extracts OCR data with page dimensions and bounding boxes, identifies the patient/member ID from the extracted text, and uploads the results to Azure Blob Storage. The workflow returns the full OCR results and blob paths for downstream consumption (e.g., classification, summarization, RAG).

**Version:** 1.1.0
**Category:** Healthcare
**Workflow Type:** Graph (DAG)

---

## Inputs

| Parameter        | Type   | Required | Description                                      |
|------------------|--------|----------|--------------------------------------------------|
| `file`           | string (URI) | Yes | SAS URL to the document in Azure Blob Storage |
| `file_hash`      | string | Yes      | MD5 hash of the file (calculated by the app)     |
| `container_name` | string | Yes      | Blob storage container name for output uploads   |

---

## Execution Graph

```
file, file_hash, container_name
            |
            v
    +-------------------+
    |  node_doc_intel   |   Azure Document Intelligence OCR
    +---------+---------+
              |
              v
    +---------------------+
    | extract_member_id   |   GPT-4.1 agent extracts member/patient ID
    +---------+-----------+
              |
        +-----+------+
        v            v
+---------------+  +---------------+
| upload_ocr    |  | upload_ocr    |   Parallel blob uploads
| extraction    |  | text          |
+-------+-------+  +-------+-------+
        |                  |
        +--------+---------+
                 v
        +-----------------+
        | return_ocr_data |   Final JSON response
        +-----------------+
```

---

## Steps

### 1. `node_doc_intel` — Azure Document Intelligence OCR

- **Type:** Tool
- **Tool:** `extract_layout_with_chunks` (via `azure_doc_intel` connection)
- **Dependencies:** None (entry point)

Sends the document URL to Azure Document Intelligence and runs layout analysis. Extracts:

- Full OCR text content
- Page dimensions (width/height per page)
- Bounding box coordinates for words, lines, and paragraphs
- Chunk segmentation of the document

**Output:** Structured JSON with text, pages, bounding boxes, and chunks (`node_doc_intel_result`).

---

### 2. `extract_member_id` — LLM Agent for Member ID Extraction

- **Type:** Intelligence (AI agent)
- **Agent:** `ExtractMemberIDfromOCR`
- **Model:** `gpt-4.1` (temperature: 0)
- **Execution Strategy:** ReAct (max 25 steps)
- **Dependencies:** `node_doc_intel`

An LLM agent receives the OCR text and parses it to find a patient/member identifier. The agent looks for labels such as:

- Member ID, Member #, MBI
- Patient ID, Subscriber ID, ID Number

Accepts various ID formats: numeric, alphanumeric, or hyphenated (e.g., `MCH-123456`, `1EG4-TE5-MK72`, `123456789`).

**Output:**

```json
{
  "member_id": "<extracted value or UNKNOWN>",
  "extraction_source": "ocr_text_parsing"
}
```

Falls back to `"UNKNOWN"` if no ID is found.

---

### 3. `upload_ocr_extraction_blob` — Upload Full OCR Extraction

- **Type:** Tool
- **Tool:** `upload_file` (blob storage)
- **Dependencies:** `node_doc_intel`, `extract_member_id`

Uploads the **complete OCR extraction** (including bounding boxes, page dimensions, and chunks) as a JSON file.

- **Blob path:** `{member_id}/{file_hash}_ocr.json`
- **Content:** Full OCR result, JSON-serialized and base64-encoded

Use case: downstream consumers that need spatial/layout information (e.g., document viewer with bounding-box highlights, citation navigation).

---

### 4. `upload_ocr_text_blob` — Upload OCR Text Only

- **Type:** Tool
- **Tool:** `upload_file` (blob storage)
- **Dependencies:** `node_doc_intel`, `extract_member_id`

Uploads **only the text content** from the OCR result (no layout metadata).

- **Blob path:** `{member_id}/{file_hash}_ocr_text.json`
- **Content:** OCR text content, base64-encoded

Use case: lightweight artifact for text-based downstream tasks (classification, summarization, RAG chunking).

> Steps 3 and 4 run **in parallel** since they share the same dependencies.

---

### 5. `return_ocr_data` — Final Output

- **Type:** Output
- **Dependencies:** `upload_ocr_extraction_blob`, `upload_ocr_text_blob`, `extract_member_id`

Returns a JSON response containing all results:

```json
{
  "success": true,
  "member_id": "<extracted ID>",
  "ocr_data": { "/* full OCR extraction */" },
  "file_hash": "<input hash>",
  "container_name": "<input container>",
  "ocr_upload_path": "<member_id>/<file_hash>_ocr.json",
  "ocr_text_path": "<member_id>/<file_hash>_ocr_text.json",
  "extraction_timestamp": "<workflow execution timestamp>"
}
```

This gives callers:
- Inline access to OCR data (no blob fetch needed for immediate use)
- Blob paths for later retrieval
- Correlation back to the original file and patient

---

## Design Decisions

### Member ID as folder key
Documents are organized by patient in blob storage (`{member_id}/`), enabling per-patient retrieval. The `UNKNOWN` fallback ensures the workflow never fails due to a missing ID.

### Two blob artifacts
Separating the full OCR extraction (with spatial data) from plain text lets downstream workflows choose the appropriate fidelity:
- A classifier or summarizer only needs text
- A document viewer with citation highlights needs bounding boxes and page dimensions

### Inline OCR data in output
The full OCR result is both stored in blob storage and returned inline. This lets the next workflow in a chain consume it immediately without a blob fetch round-trip.

### Base64 encoding for uploads
The `b64encode` filter is applied because the `upload_file` tool expects binary-safe content encoding for JSON payloads that may contain special characters or nested structures.

---

## Downstream Usage

This workflow is designed as the **first stage** in a document processing pipeline. Its output feeds into:

1. **Classification workflows** — categorize the document type using the OCR text
2. **Summarization workflows** — generate structured summaries with chunk tracking
3. **RAG ingestion** — chunk and embed the OCR text for retrieval-augmented generation
4. **Document viewers** — render the original document with bounding-box overlays for citations
