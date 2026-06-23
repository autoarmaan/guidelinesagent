import os

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

from vector_store import ingest_documents, query_documents

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
load_dotenv(_env_path, override=True)

app = FastAPI(title="Guidelines Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "documents")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

SYSTEM_PROMPT = """You are a compliance and security expert assistant. Your job is to answer questions about organizational guidelines, policies, and security practices based on the provided context documents.

Rules:
- Only answer based on the provided context. If the context doesn't contain enough information, say so.
- Be precise and cite specific policy sections when possible.
- For yes/no questions, give a clear answer then explain.
- Keep answers concise but thorough."""


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    # Retrieve relevant document chunks
    relevant_chunks = query_documents(request.message, OPENAI_API_KEY)

    if not relevant_chunks:
        return ChatResponse(
            answer="No documents have been ingested yet. Please upload guideline documents first.",
            sources=[],
        )

    context = "\n\n---\n\n".join(relevant_chunks)

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Context from guideline documents:\n\n{context}\n\n---\n\nQuestion: {request.message}",
            },
        ],
        temperature=0.2,
    )

    return ChatResponse(
        answer=response.choices[0].message.content,
        sources=relevant_chunks[:3],
    )


@app.post("/api/ingest")
async def ingest():
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    os.makedirs(DOCUMENTS_DIR, exist_ok=True)
    count = ingest_documents(DOCUMENTS_DIR, OPENAI_API_KEY)
    return {"message": f"Ingested {count} chunks from documents in /documents folder"}


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")

    os.makedirs(DOCUMENTS_DIR, exist_ok=True)
    file_path = os.path.join(DOCUMENTS_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    return {"message": f"Uploaded {file.filename}"}


@app.get("/api/health")
async def health():
    return {"status": "ok"}
