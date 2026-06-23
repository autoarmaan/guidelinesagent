# AI Studio Workflow Recommendation: Guidelines Compliance Chatbot

## Objective

Build a RAG-powered chatbot on the Autonomize AI Studio platform that:

1. Answers compliance and security questionnaire questions using ingested company guideline documents
2. Cites specific source chunks/locations where the answer was found

---

## Recommended Architecture

Two workflows working together:

```
                    ONE-TIME SETUP                              RUNTIME (per question)
 ┌─────────────────────────────────┐        ┌───────────────────────────────────────────────┐
 │  RAG Ingestion Large Files      │        │  Detailed Summary Agent (customized)          │
 │                                 │        │                                               │
 │  .docx/.pdf guideline docs      │        │  User Question                                │
 │         │                       │        │       │                                       │
 │         v                       │        │       v                                       │
 │  Azure Blob Storage             │        │  LLM Agent (GPT-4.1)                          │
 │         │                       │        │    ├── vector_store_search tool                │
 │         v                       │        │    │     └── queries guideline chunks          │
 │  OCR (Azure Doc Intelligence)   │        │    ├── generates grounded answer              │
 │         │                       │        │    └── cites source sections                   │
 │         v                       │        │       │                                       │
 │  Text Chunking (1000 chars,     │        │       v                                       │
 │    200 overlap)                 │        │  Chat Output                                  │
 │         │                       │        │    ├── include_citations: true                 │
 │         v                       │        │    └── markdown formatted response            │
 │  Embedding Generation           │        │                                               │
 │         │                       │        └───────────────────────────────────────────────┘
 │         v                       │
 │  Vector Store (with metadata:   │
 │    file hash, page boundaries,  │
 │    chunk UUIDs)                 │
 └─────────────────────────────────┘
```

---

## Workflow 1: Document Ingestion — `RAG Ingestion Large Files`

**Purpose:** Ingest company guideline documents (.docx, .pdf) into a vector store for retrieval.

**Template:** `rag_ingestion_large_files` (v2.0.0, 8 steps)

### Pipeline Steps

| Step | Component | Description |
|------|-----------|-------------|
| 1. List Source Documents | `list_files` (Azure Blob connector) | Lists all guideline files from blob storage |
| 2. Download Files | `download_file` | Downloads files to intermediate storage (parallel, max 5 concurrent) |
| 3. OCR Documents | `extract_layout_with_chunks` (Azure Doc Intel) | Full document OCR preserving layout |
| 4. Split Text Chunks | `text_splitter` | Splits OCR output into chunks (configurable size/overlap) |
| 5. Generate Embeddings | `batch_embedder` | Generates vector embeddings for each chunk |
| 6. Build Vector Documents | `document_builder` | Assembles chunks + embeddings + metadata (file hash, page boundaries, chunk UUIDs) |
| 7. Store Vectors | `upsert_documents` (vector_store connector) | Stores into the vector collection |
| 8. Pipeline Summary | output | Reports files processed, documents stored, errors |

### Key Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `connection_name` | *(required)* | Azure Blob Storage connection with guideline docs |
| `collection_name` | *(required)* | Vector store collection name (e.g., `company-guidelines`) |
| `chunk_size` | 1000 | Max characters per text chunk |
| `chunk_overlap` | 200 | Overlap between adjacent chunks |
| `max_concurrent` | 3 | Parallel batch operations |
| `max_files` | 100 | Max files to process |
| `embedding_provider` | auto | Resolved at runtime |
| `embedding_model` | auto | Resolved at runtime |

### Why This Template

- File-level batching (efficient — ~24 child workflows for 4 files vs ~930+ at page-level)
- Rich metadata stored with each chunk (file hash, page boundaries, chunk UUIDs) — this is what enables **precise source citations** in the chatbot
- Retry logic with exponential backoff on downloads
- Continues on OCR errors (doesn't fail the whole batch)

---

## Workflow 2: Chatbot — `Detailed Summary Agent` (Customized)

**Purpose:** Chat interface that answers compliance questions using vector-retrieved guideline chunks, with source citations.

**Template:** `detailed_summary_agent` (v1.0.0, 3 steps)

### Pipeline Steps

| Step | Component | Description |
|------|-----------|-------------|
| 1. Template Renderer | `template_renderer` | Formats user input into structured prompt context |
| 2. LLM Agent | `llm_agent` (GPT-4.1, Azure OpenAI) | Retrieves chunks via vector_store_search, generates grounded answer |
| 3. Chat Output | `chat_output` | Formats response with markdown and citations |

### Required Customizations

#### 1. System Prompt — Change from Clinical to Compliance

Replace the medical summary prompt with:

```
You are a compliance and security policy expert. You answer questions about
company guidelines, policies, and procedures by searching the organization's
guideline document vector store.

## Workflow
1. Analyze the user's question to identify relevant policy areas.
2. Use vector_store_search to retrieve relevant guideline chunks.
3. Synthesize a clear, accurate answer grounded ONLY in the retrieved content.

## Citation Rules
- ALWAYS cite the specific source document and section for every claim.
- Format citations as: [Source: <document name>, <section/page>]
- If multiple chunks support an answer, cite all of them.
- If retrieved chunks do not contain enough information, say so explicitly.
  Do NOT fabricate or infer policy details.

## Answer Format
- Lead with a direct yes/no or summary answer.
- Follow with supporting details and policy references.
- Use bullet points for multi-part answers.
- Quote exact policy language when relevant.

## Rules
- ONLY use information from retrieved guideline chunks — NO HALLUCINATION.
- If the question is outside the scope of available guidelines, state that clearly.
- Be precise with policy language — do not paraphrase in ways that change meaning.
```

#### 2. Chat Output — Enable Citations

Change in the chat output config:

```yaml
include_citations: true    # was: false
include_metadata: true     # was: false — shows source chunk metadata
```

#### 3. Add Conversation Memory

Add to the agent config (currently `null`):

```yaml
memory:
  type: conversation_buffer
  config: {}
  enabled: true
  collection_name: null
  window_size: 10
```

This enables multi-turn follow-up questions (e.g., "What about the retention period for that?").

#### 4. Vector Store Tool — Point to Guidelines Collection

Update the vector store tool config:

```yaml
tools:
  - name: Vector Store
    type: component
    config:
      operation: search
      collection_name: company-guidelines    # match your ingestion collection_name
      limit: 10
      content_key: text
      expose_fields:
        - query
        - limit
        - filter
      component: vector_store
```

#### 5. Inputs — Simplify for Chat

Replace the medication-specific inputs with a simple chat message:

```yaml
inputs:
  message:
    type: string
    description: User's compliance question
    required: true
  collection_name:
    type: string
    description: Vector collection to search
    default: company-guidelines
```

---

## LLM Model Options

The platform supports multiple providers. Recommended configurations:

| Provider | Model | Best For | Notes |
|----------|-------|----------|-------|
| **Azure OpenAI** | `gpt-4.1` | Default, balanced speed/quality | Already configured in templates |
| **OpenAI** | `gpt-4.1` | Same model, direct API | Requires OPENAI_API_KEY |
| **Anthropic** | `claude-sonnet-4-20250514` | Strong reasoning, nuanced answers | Requires ANTHROPIC_API_KEY |
| **Google AI** | Gemini models | Alternative option | Requires Google auth |

**Recommendation:** Start with `azure_openai` / `gpt-4.1` (the platform default). It has a 1M token context window, strong instruction following, and is already wired into the templates. Switch to Anthropic Claude if you need stronger reasoning for complex multi-policy questions.

LLM config in the agent:

```yaml
llm_config:
  provider: azure_openai
  model: gpt-4.1
  temperature: 0.2          # low temperature for factual, grounded answers
  max_tokens: 16000
  top_p: 1.0
```

---

## Implementation Steps

### Phase 1: Document Ingestion

1. Upload guideline documents (.docx, .pdf) to Azure Blob Storage
2. Create a vector store collection (e.g., `company-guidelines`)
3. Create a workflow from the `rag_ingestion_large_files` template:
   ```bash
   autonomize create rag_ingestion_large_files
   ```
4. Run the ingestion workflow:
   ```bash
   autonomize run <workflow-id> \
     --input connection_name=<blob-connection> \
     --input collection_name=company-guidelines
   ```
5. Verify ingestion completed:
   ```bash
   autonomize exec-status <execution-id>
   ```

### Phase 2: Chatbot Workflow

1. Create a workflow from the `detailed_summary_agent` template:
   ```bash
   autonomize create detailed_summary_agent
   ```
2. Export and customize the workflow spec:
   ```bash
   autonomize export <workflow-id> -o chatbot-spec.yaml
   ```
3. Apply the customizations listed above (system prompt, citations, memory, inputs)
4. Import the updated spec:
   ```bash
   autonomize import chatbot-spec.yaml
   ```
5. Test with a sample question:
   ```bash
   autonomize run <workflow-id> \
     --input message="What is our data retention policy for PHI?"
   ```

### Phase 3: Integration with Frontend (optional)

The chatbot workflow can be called via the AI Studio API from the existing React frontend, replacing the current direct-to-OpenAI approach in `backend/main.py`.

---

## Comparison: AI Studio vs Current Local Implementation

| Aspect | Current (Local RAG) | AI Studio Workflows |
|--------|--------------------|--------------------|
| **Document parsing** | Custom Python docx parser | Azure Doc Intelligence OCR (handles PDFs, scans, tables) |
| **Vector store** | ChromaDB (local, embedded) | Managed vector store with rich metadata |
| **Embeddings** | OpenAI text-embedding-3-small | Configurable (OpenAI, Azure, Autonomize BGE) |
| **LLM** | GPT-4o-mini | GPT-4.1, Claude Sonnet 4, or others |
| **Citations** | Top 3 source chunks returned | Built-in citation support with chunk metadata (file, page, section) |
| **Conversation memory** | None (single-turn) | Configurable buffer window (multi-turn) |
| **Scalability** | Single machine | Cloud-native, parallel batch processing |
| **Monitoring** | None | Execution logs, traces, metrics |

---

## Documents to Ingest

Based on the current project, these guideline documents should be ingested:

- `Autonomize - Data Retention, Archival, And Purge Policy.docx`
- `questionnaire-v3-AI.docx`
- Any additional compliance/security policy documents

---

## Autonomize CLI Quick Reference

```bash
# Environment setup
autonomize env add my-env --from autonomize.env
autonomize env use my-env
autonomize login

# Workflows
autonomize list                              # List all workflows
autonomize templates list                    # List available templates
autonomize create <template-name>            # Create workflow from template
autonomize export <workflow-id> -o spec.yaml # Export workflow spec
autonomize import spec.yaml                  # Import workflow spec
autonomize run <workflow-id> --input k=v     # Run a workflow
autonomize exec-status <execution-id>        # Check execution status
autonomize logs <execution-id>               # View execution logs

# Model providers
autonomize model-providers list              # List available LLM providers
autonomize model-providers show openai       # Show provider details
```
