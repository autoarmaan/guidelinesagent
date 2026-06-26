# Knowledge Center — Chunk Response Schema

How to retrieve chunks and what they contain, for building citations in the frontend.

## How to Get Chunks

Chunks are returned in the workflow execution response when the agent calls `knowledge_retrieval`. They are **not** available via a standalone KC API endpoint — you get them as part of a query.

### Response Location

The chunks live inside the workflow execution result at this path:

```
result.new_messages[*]
  → find part where part_kind == "tool-return"
    AND tool_name == "use_Knowledge_Retrieval_compliance_guidelines"
  → .content.result.retrieved_documents[]
```

### Tool Call Details

The agent calls the tool with:
```json
{
  "tool_name": "use_Knowledge_Retrieval_compliance_guidelines",
  "args": {
    "query": "data retention policy",
    "knowledge_source": "compliance_guidelines"
  }
}
```

The tool returns:
```json
{
  "success": true,
  "result": {
    "query": "data retention policy",
    "retrieved_documents": [ ...chunks... ],
    "context": "...concatenated chunk text (what the LLM sees)...",
    "count": 10
  }
}
```

## Chunk Schema

Each item in `retrieved_documents` has this shape:

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
    "file_path": "kc-<project-id>/kc-<dataset-id>/...",
    "index": 0,
    "is_active": true,
    "page_number": 2,
    "source": "uploads/Autonomize \u2013 Data Retention, Archival, And Purge Policy.pdf",
    "strategy": "recursive",
    "total_chunks": 2
  },
  "score": 0.6168754
}
```

## Field Reference

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `content` | string | The actual chunk text extracted from the PDF |
| `metadata` | object | All metadata about the chunk (see below) |
| `score` | float | Cosine similarity score (0-1, higher = more relevant) |

### Metadata Fields

| Field | Type | Description |
|-------|------|-------------|
| `page_number` | int | PDF page the chunk came from (1-indexed) |
| `chunk_index` | int | Index of this chunk within its page (0-indexed) |
| `total_chunks` | int | How many chunks the page was split into (1 or 2 observed) |
| `index` | int | Same as chunk_index |
| `char_count` | int | Character count of the chunk content |
| `source` | string | Original filename (e.g. `"uploads/Autonomize – Data Retention..."`) |
| `document_id` | string (UUID) | KC document ID |
| `dataset_id` | string (UUID) | KC dataset ID |
| `file_hash` | string | SHA-256 hash of the source PDF |
| `file_path` | string | Internal KC blob path |
| `strategy` | string | Chunking strategy used (observed: `"recursive"`) |
| `is_active` | bool | Whether the chunk is active in the index |
| `bounding_region` | object | Physical location on the PDF page |

### Bounding Region

| Field | Type | Description |
|-------|------|-------------|
| `page_number` | int | Same as top-level page_number |
| `polygon` | array of `{x, y}` | Four corner points (top-left, top-right, bottom-right, bottom-left) in pixel coordinates |

The polygon can be used to highlight the exact source region on the PDF in the frontend.

## Observed Chunk Characteristics

From the `Autonomize – Data Retention, Archival, And Purge Policy.pdf` (7-page document):

- **Chunking strategy**: `recursive` (recursive text splitting)
- **Chunks per page**: 1-2 chunks per page
- **Chunk sizes**: 269-993 characters (avg ~700)
- **Total chunks**: ~12 across 7 pages
- **Score range**: 0.48-0.62 for a broad policy question
- **Limit**: 10 chunks returned per query (configured in workflow tool config)

## Useful Fields for Frontend Citations

For building a citation UI, the most useful fields are:

1. **`source`** — display the document name
2. **`page_number`** — "Page 3"
3. **`content`** — show a preview/snippet of the chunk text
4. **`score`** — rank or filter by relevance
5. **`bounding_region.polygon`** — highlight source region on a PDF viewer
