# Document Intelligence & OCR Chunking Exploration

Results from exploring OCR chunking options for the compliance guidelines agent.

---

## 1. Current State: How KC Chunks Work

The compliance chatbot (`workflows/compliance-chatbot.yaml`) uses Knowledge Center's `knowledge_retrieval` tool to search the `compliance_guidelines` dataset. KC chunks are produced internally during PDF ingestion.

### KC Chunk Schema

Retrieved from actual workflow execution (`debug_response.json`):

```json
{
  "content": "1. Purpose\nThis document serves as Autonomize's...",
  "metadata": {
    "bounding_region": {
      "page_number": 2,
      "polygon": [
        { "x": 303.0, "y": 416.0 },
        { "x": 625.0, "y": 418.0 },
        { "x": 625.0, "y": 486.0 },
        { "x": 302.0, "y": 485.0 }
      ]
    },
    "char_count": 985,
    "chunk_index": 0,
    "dataset_id": "45e640ac-6d10-454f-8289-8d43d9904dab",
    "document_id": "3ac252a7-e9cc-41d9-a219-fbfc875db163",
    "file_hash": "9d983e43abd5bf97a2839379e56e3f998afb5dafa...",
    "page_number": 2,
    "source": "uploads/Autonomize - Data Retention, Archival, And Purge Policy.pdf",
    "strategy": "recursive",
    "total_chunks": 2
  },
  "score": 0.6168754
}
```

### KC Chunk Characteristics (Data Retention Policy, 7-page PDF)

| Metric | Value |
|--------|-------|
| Total chunks | ~12 |
| Chunks per page | 1-2 |
| Chunk sizes | 269-993 chars (avg ~700) |
| Strategy | `recursive` (recursive text splitting) |
| Score range | 0.42-0.62 for a broad query |
| Retrieval limit | 10 per query (configured in workflow) |
| Access method | Semantic search only (no "get all chunks" API) |

### KC Limitations

- **No standalone chunk listing API** - chunks only come back as search results
- Cannot retrieve all chunks for a document (only top-N by similarity)
- Coarse granularity: 1-2 chunks per page loses structural detail
- No character-level offsets for precise text positioning

---

## 2. OCR Summarizer Workflows (Appeals Team)

Two existing workflows that consume OCR output from a separate upstream pipeline. These are **consumers** of OCR data, not producers.

### Workflow A: Chunk Tracking (3-step deterministic pipeline)

**File:** `ocr_summarizer_with_chunk_tracking.yaml`

```
[member_id, file_hash]
        |
        v
 download_ocr_file      <- TOOL step (azure_blob download, no LLM)
        |
        v
 summarize_with_chunks   <- LLM AGENT (gpt-4, data injected into prompt)
        |
        v
 output_summary          <- OUTPUT (markdown, chat_output)
```

- **Architecture**: Separate download step -> LLM processes pre-loaded data
- **Model**: gpt-4
- **Output**: Freeform markdown with `## CATEGORY_NAME` headers
- **Categories**: Key Stakeholders, Case Timeline, Dates, Patient Demographics, Medical Presentation, Clinical Course, Comprehensive Medical History
- **Chunk citation format**: `[chunk_id: XXXXX]`

### Workflow B: Categorical Output (2-step agentic pipeline)

**File:** `ocr_summarizer_with_categorical_output.yaml`

```
[member_id, file_hash]
        |
        v
 summarize_with_chunks   <- LLM AGENT (gpt-5.4, autonomously calls download_file)
        |
        v
 output                  <- OUTPUT (raw data passthrough)
```

- **Architecture**: Agent autonomously fetches file via tool use (ReAct loop)
- **Model**: gpt-5.4
- **Output**: Structured JSON grouped by page number, with `output_schema`
- **Categories**: Medical Conditions, Medications, Tests & Procedures, Anatomy, Provider Notes, Discharge Summary, Specialist Consultations, H&P, Emergency Room
- **PHI**: Explicitly excluded
- **Chunk citation format**: `{"chunk_id": "XXXXX", "text": "excerpt"}`

### Key Insight

These workflows read `{member_id}/{file_hash}_ocr.json` from blob container `appeals-uploads`. The upstream OCR pipeline that **produces** those JSON files is not defined in these YAMLs. They are just categorization/summarization layers.

---

## 3. Azure Document Intelligence in AI Studio

### Connector & Tools Available

AI Studio has an `azure_doc_intel` connector (category: `ocr`) with **4 tools**:

| Tool | Description | Granularity |
|------|-------------|-------------|
| `extract_text` | Plain text extraction | Lowest - raw text only |
| `extract_layout` | Text + tables + structure, lines per page | Medium |
| **`extract_layout_with_chunks`** | Layout + line-level chunk metadata with bounding regions | **Highest** |
| `extract_layout_from_pages` | Same as above but for pre-rendered page images | For image-based docs |

### Tool Input Schema: `extract_layout_with_chunks`

```json
{
  "document": "string (URL, file://, base64, or cloud URI)",
  "mime_type": "string (default: application/pdf)",
  "file_hash": "string (optional, for traceability)",
  "include_page_documents": "boolean (default: false)"
}
```

### Tool Output Schema: `extract_layout_with_chunks`

```json
{
  "content": "string (full text)",
  "file_hash": "string",
  "pages": [
    {
      "page_number": 1,
      "lines": ["string array"],
      "page_content": "string",
      "chunks_metadata": [
        {
          "chunk_uuid": "string (UUID)",
          "content": "string",
          "text": "string",
          "begin_offset": 0,
          "end_offset": 10,
          "bounding_region": {
            "page_number": 1,
            "polygon": [{"x": 0.0, "y": 0.0}, ...]
          }
        }
      ]
    }
  ],
  "page_contents": ["string array"],
  "page_metadata": [...],
  "page_documents": [...],
  "tables": [{"row_count": 0, "col_count": 0}]
}
```

### Connections (Health Status)

Tested 2026-06-25:

| Connection | ID | Status |
|------------|-----|--------|
| **My Azure Document Intelligence** | `26e54191-86a1-4e45-a12d-039359af4c01` | **HEALTHY** (2.2s) |
| **MI Test - My Azure Document Intelligence** | `9e745959-f740-4a40-9add-c3a38a429241` | **HEALTHY** (2.4s) |
| azure_doc_intel_1779953975 | e61ab062-... | UNHEALTHY |
| azure_doc_intel_1779953742 | 6fee349e-... | UNHEALTHY |
| azure_doc_intel_1779953677 | 96c381f9-... | UNHEALTHY |
| azure_doc_intel_1779953673 | b1c908ff-... | UNHEALTHY |
| azure_doc_intel_1779953662 | 20bda1a6-... | UNHEALTHY |
| azure_doc_intel_1779953618 | ad41b4fb-... | UNHEALTHY |
| azure_doc_intel_1779953569 | 2557c13e-... | UNHEALTHY |
| azure_doc_intel (oldest) | c8c3149b-... | UNHEALTHY |

Healthy endpoint: `https://platform-integration.cognitiveservices.azure.com/`

---

## 4. Test Execution Results

### Method

Created an agent-based workflow that calls `extract_layout_with_chunks` via the healthy "My Azure Document Intelligence" connection. Ran against the 7-page `Autonomize - Data Retention, Archival, And Purge Policy.pdf` (136KB) stored in `guideline-documents` blob container.

- **Workflow ID**: `7dbe6f18-134b-46b8-b399-424e5a87a87a`
- **Connection used**: `My Azure Document Intelligence` (`26e54191-86a1-4e45-a12d-039359af4c01`)
- **Execution time**: ~7 seconds for OCR + agent processing
- **Raw result saved**: `ocr_chunks_raw.json` (342KB), `ocr_agent_result.json` (422KB)

### Doc Intelligence Output Summary

| Metric | Value |
|--------|-------|
| Total pages | 7 |
| **Total chunks** | **209** |
| Chunks per page | 11-51 |
| Chunk sizes | 2-88 chars (avg 34, median 24) |
| Granularity | **Line-level** (1 chunk = 1 line of text) |
| IDs | UUID per chunk |
| Positioning | `begin_offset` / `end_offset` (character-level) + bounding polygon |

### Per-Page Breakdown

| Page | Chunks | Lines |
|------|--------|-------|
| 1 | 27 | 27 |
| 2 | 29 | 29 |
| 3 | 51 | 51 |
| 4 | 32 | 32 |
| 5 | 32 | 32 |
| 6 | 27 | 27 |
| 7 | 11 | 11 |

### Sample Chunk

```json
{
  "chunk_uuid": "75469878-c6ea-4b34-87ba-689dbd6285bf",
  "content": "Autonomize",
  "text": "Autonomize",
  "begin_offset": 0,
  "end_offset": 10,
  "bounding_region": {
    "page_number": 1,
    "polygon": [
      {"x": 2.9654, "y": 1.0456},
      {"x": 5.5775, "y": 1.1029},
      {"x": 5.5728, "y": 1.5135},
      {"x": 2.9654, "y": 1.4944}
    ]
  }
}
```

---

## 5. Side-by-Side Comparison

| Dimension | Doc Intelligence (OCR) | KC (Knowledge Center) |
|-----------|----------------------|----------------------|
| **Total chunks** | 209 | ~12 |
| **Granularity** | Line-level | Page-section level |
| **Chunk size** | 2-88 chars (avg 34) | 269-993 chars (avg ~700) |
| **Resolution ratio** | **~17x more granular** | Baseline |
| **Positioning** | `begin_offset`/`end_offset` + polygon | Polygon only |
| **IDs** | UUID per chunk | `chunk_index` (0 or 1 per page) |
| **Retrieval** | Full document extraction (all chunks) | Semantic search (top-N only) |
| **Semantic coherence** | Low (individual lines) | Higher (paragraph-level) |
| **RAG suitability** | Needs re-chunking for meaningful retrieval | Ready for retrieval as-is |
| **Citation precision** | Exact line + character position | Page + bounding box |
| **Table awareness** | Tables extracted separately | Tables mixed into text chunks |

---

## 6. Observations & Tradeoffs

### Doc Intelligence Strengths
- Full document extraction - get every line, no information lost
- Precise positioning (character offsets + polygons) for PDF highlighting
- Table extraction as separate structured data
- UUID per chunk for reliable traceability
- No dependency on semantic search - deterministic, complete output

### Doc Intelligence Weaknesses
- Line-level chunks are too granular for RAG (e.g., `"Data"`, `"PHI"`, `"Included"` as standalone chunks)
- Would need a re-chunking layer to create semantically meaningful units
- 209 chunks for a 7-page doc could be noisy without grouping

### KC Strengths
- Chunks are already semantically coherent (paragraph/section level)
- Ready for RAG retrieval without post-processing
- Integrated with vector search (similarity scoring)
- Simpler pipeline (ingestion handles everything)

### KC Weaknesses
- No way to retrieve all chunks for a document
- Coarse granularity loses structural detail
- Only 1-2 chunks per page - may miss content in retrieval
- Can't control chunking strategy

---

## 7. Possible Next Steps

### A. Hybrid approach
Use Doc Intelligence for raw OCR, then apply custom chunking (paragraph-level, section-level, or sliding window) to create chunks that are both semantically meaningful AND precisely locatable on the PDF. Best of both worlds.

### B. Doc Intel + custom vector store
Run Doc Intelligence OCR -> custom chunking -> embed and store in a vector DB (Qdrant, ChromaDB, or KC) with the bounding region metadata preserved. Gives full control over chunk granularity.

### C. Doc Intel as pre-processor for KC
Use Doc Intelligence to extract text, re-chunk at desired granularity, then feed into KC for indexing. KC handles retrieval, but with better chunks.

### D. Full document extraction workflow
Build a workflow similar to the OCR summarizers that runs Doc Intelligence on any uploaded PDF and stores the structured output (with all chunk metadata) for downstream use.

### E. Stay with KC, increase retrieval limit
Simplest option: increase the `limit` from 10 to 20-30 in the knowledge_retrieval tool config. May recover more content per query without changing the pipeline.

---

## 8. Test Artifacts

| File | Description |
|------|-------------|
| `ocr_chunks_raw.json` | Raw Doc Intelligence output (209 chunks, 342KB) |
| `ocr_agent_result.json` | Full workflow execution response (422KB) |
| `ocr_chunks_result.json` | Execution metadata (status, timing) |
| `debug_response.json` | Compliance chatbot response with KC chunks |
| `KC_CHUNK_SCHEMA.md` | KC chunk schema documentation |

## 9. Test Workflows Created in AI Studio

These were created for testing and can be deleted:

| Name | ID | Purpose |
|------|-----|---------|
| OCR Test - Extract Chunks v2 | `1bf5bfc9-75ee-4dd1-a997-5349e1b05d08` | Tool-step test (output went to data:// URI) |
| OCR Test Agent v3 | `7dbe6f18-134b-46b8-b399-424e5a87a87a` | Agent-based test (successful, inline output) |
| OCR Test - Extract Chunks | `d6db6a32-0e21-4563-a41f-6e74204a7da5` | First attempt (template variable issue) |
