# Guidelines Agent - Design Document

## Problem Statement

Multiple clients request clarity on Autonomize's PHI protections, model governance, and data security practices. These arrive as lengthy security questionnaires (50-100+ questions) that must be answered by referencing internal guideline documents (data retention policies, security frameworks, compliance procedures, etc.).

Today this is manual: someone reads the questionnaire, searches through policy docs, and writes answers. The goal is to automate this with a RAG chatbot that can answer compliance questions grounded in our actual policy documents.

## Architecture Overview

```
┌─────────────────────┐     HTTP/JSON     ┌──────────────────────────┐
│   React Frontend    │ ◄──────────────► │   FastAPI Backend        │
│   (Vite, port 5173) │                   │   (Uvicorn, port 8000)   │
│                     │                   │                          │
│  - Upload .docx     │                   │  /api/upload  - store    │
│  - Trigger ingest   │                   │  /api/ingest  - parse,   │
│  - Chat UI          │                   │                embed,    │
│                     │                   │                store     │
│                     │                   │  /api/chat    - retrieve │
│                     │                   │                + LLM     │
└─────────────────────┘                   └──────────┬───────────────┘
                                                     │
                                          ┌──────────▼───────────────┐
                                          │  ChromaDB (embedded)     │
                                          │  - Vector store          │
                                          │  - Persistent on disk    │
                                          │  - OpenAI embeddings     │
                                          └──────────────────────────┘
```

## Design Choices

### 1. Document Parsing: Section-Aware Extraction

**Choice**: Structure-preserving section parser rather than naive text splitting.

**Why**: Policy documents have hierarchical structure (sections, subsections, tables) that carries semantic meaning. A section titled "7.1 Purge Triggers" under "7. Data Purge and Deletion Policy" is fundamentally different context than a flat text chunk that happens to contain some of those words.

**How it works** (`document_loader.py`):
- Detects headings via Word styles (`Heading 1`, `Heading 2`, etc.)
- Also detects *implicit* headings — numbered paragraphs like "5.1 Retention Timeframes" styled as normal text (common in policy docs)
- Maintains a heading stack to build hierarchical paths: `"Data Purge and Deletion Policy > Purge Triggers"`
- Converts tables to markdown format so tabular data (retention timeframes, data classifications) is preserved in a format the LLM can reason over
- Merges consecutive same-level headings (handles multi-line titles split across paragraphs)

**Alternative considered**: Simple word-count chunking with overlap (the legacy `chunk_text` function still exists for vector store compatibility). This loses section boundaries and can split a table or policy statement across two chunks, degrading retrieval quality.

### 2. Vector Store: ChromaDB (Embedded)

**Choice**: ChromaDB in persistent embedded mode (no separate server).

**Why**:
- Zero infrastructure overhead — runs in-process, stores to `./chroma_db/` on disk
- Sufficient for the expected scale (dozens of policy documents, hundreds of chunks)
- Built-in support for OpenAI embedding functions
- Easy to replace later if needed (the interface is simple: ingest, query)

**Embedding model**: `text-embedding-3-small` — good quality-to-cost ratio for retrieval, 1536 dimensions.

**Alternative considered**: FAISS (no persistence without extra code), Pinecone (external service, unnecessary complexity at this scale), pgvector (requires Postgres).

### 3. LLM: GPT-4o-mini

**Choice**: OpenAI `gpt-4o-mini` for answer generation.

**Why**:
- Fast and cheap for a chat-style Q&A workload
- Good instruction following for the structured compliance answers we need
- Context window (128k) is more than sufficient for retrieved chunks
- Low temperature (0.2) to keep answers factual and grounded

**System prompt design**: The prompt enforces grounding — the model must answer from provided context only, cite specific policy sections, and give clear yes/no answers before explaining. This is critical for compliance use cases where hallucinated policy details could be harmful.

### 4. Retrieval Strategy: Top-5 Chunks

**Choice**: Retrieve top 5 most similar chunks, pass all as context to the LLM.

**Why**: Policy questions often span multiple sections. "What are our data retention requirements?" touches the retention policy, archival timelines, and purge triggers. Retrieving 5 chunks gives enough coverage without flooding the context.

**Returned to user**: The top 3 source chunks are returned alongside the answer for transparency. Users can expand "Sources" to verify the answer is grounded.

### 5. Frontend: Minimal React + Vite

**Choice**: Single-page React app with no component library.

**Why**:
- The UI is intentionally simple: upload area, ingest button, chat window
- No routing needed — it's a single-view tool
- Vanilla CSS keeps the bundle small and avoids framework lock-in
- Vite for fast dev server and builds

**UI flow**:
1. Upload `.docx` guideline documents via file picker
2. Click "Ingest Documents" to parse + embed them
3. Type questions in the chat and get grounded answers with source citations

### 6. API Design

Three endpoints, each with a single responsibility:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/upload` | POST | Accept and store a `.docx` file |
| `/api/ingest` | POST | Parse all docs in `/documents`, embed, store in ChromaDB |
| `/api/chat` | POST | RAG query: retrieve relevant chunks + LLM answer |
| `/api/health` | GET | Liveness check |

Upload and ingest are separated so users can upload multiple documents before triggering a single ingestion pass. Ingestion is destructive (drops and recreates the collection) to keep things simple — re-ingest is idempotent.

### 7. Environment & Config

- `OPENAI_API_KEY` loaded from `.env` at project root via `python-dotenv`
- Documents stored in `documents/` directory (gitignored content, tracked folder)
- ChromaDB persists to `backend/chroma_db/` (gitignored)
- CORS configured for `localhost:5173` only

## File Structure

```
guidelinesagent/
├── backend/
│   ├── main.py              # FastAPI app, endpoints, system prompt
│   ├── document_loader.py   # Section-aware .docx parser + legacy chunker
│   ├── vector_store.py      # ChromaDB wrapper (ingest + query)
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Upload/ingest controls, layout
│   │   ├── App.css           # All styles
│   │   ├── main.jsx          # React entry point
│   │   └── components/
│   │       └── ChatBot.jsx   # Chat messages + input form
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── documents/                # Guideline .docx files (user-managed)
├── .env                      # OPENAI_API_KEY + Autonomize config
└── .gitignore
```

## Future Considerations

These are not in scope now but are natural next steps:

- **Batch questionnaire mode**: Upload a questionnaire .docx and auto-answer all questions, outputting a completed document
- **Multi-turn conversation**: Add chat history to the LLM context for follow-up questions
- **Section-aware retrieval**: Use the structured section metadata (path, level) in vector search rather than flat text chunks
- **Multiple LLM providers**: Support Anthropic Claude alongside OpenAI (the Autonomize platform already uses both)
- **Answer caching**: Cache Q&A pairs to build the "compendium of Q&A that can be re-used" mentioned in the original task
- **Confidence scoring**: Flag answers where retrieved chunks have low similarity scores so a human can review
