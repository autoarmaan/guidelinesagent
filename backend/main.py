import json
import os
from urllib.parse import unquote

from azure.storage.blob import ContainerClient
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
load_dotenv(_env_path, override=True)

app = FastAPI(title="Guidelines Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKFLOW_ID = "f21caa65-d208-4de7-a257-1ab9167c8c98"


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    answer: str
    sources: list = []


def _get_token() -> str:
    """Read the stored autonomize CLI token."""
    creds_path = os.path.join(
        os.environ.get("APPDATA", ""), "autonomize", "credentials.json"
    )
    try:
        with open(creds_path) as f:
            creds = json.load(f)
        return creds["profiles"]["https://genesis.integration.autonomize.ai/studio"][
            "access_token"
        ]
    except (FileNotFoundError, KeyError):
        raise HTTPException(
            status_code=500,
            detail="Not logged in to AI Studio. Run: autonomize login",
        )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Run the AI Studio compliance chatbot workflow."""
    token = _get_token()

    import httpx

    async with httpx.AsyncClient(timeout=120.0) as client:
        exec_resp = await client.post(
            f"https://genesis.integration.autonomize.ai/studio/api/v1/workflows/{WORKFLOW_ID}/execute",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "x-organization-id": "16a74ae7-32e9-46e7-9250-2a307dfd6252",
                "x-project-id": "4df068e6-4d6b-432d-b337-df98d2a428af",
            },
            json={"context": {"message": request.message}},
        )

        if exec_resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"AI Studio error ({exec_resp.status_code}): {exec_resp.text[:500]}",
            )

        result = exec_resp.json()
        answer = _extract_answer(result)
        sources = _extract_sources(result)
        return ChatResponse(answer=answer, sources=sources)


def _extract_answer(result: dict) -> str:
    """Extract the text answer from an AI Studio execution response."""
    # Look for the last text part in new_messages (the agent's final answer)
    for key in ("output", "result"):
        if key in result and isinstance(result[key], dict):
            for msg in reversed(result[key].get("new_messages", [])):
                for part in reversed(msg.get("parts", [])):
                    if part.get("part_kind") == "text":
                        return part.get("content", "")

    # Direct content field
    if "content" in result:
        return result["content"]

    # Nested in output
    if "output" in result:
        output = result["output"]
        if isinstance(output, str):
            return output
        if isinstance(output, dict) and "content" in output:
            return output["content"]

    # Nested in result
    if "result" in result:
        r = result["result"]
        if isinstance(r, str):
            return r
        if isinstance(r, dict):
            if "content" in r:
                return r["content"]
            if "output" in r:
                o = r["output"]
                if isinstance(o, str):
                    return o
                if isinstance(o, dict) and "content" in o:
                    return o["content"]

    # Fallback: return the whole thing as JSON
    return json.dumps(result, indent=2)


def _extract_sources(result: dict) -> list:
    """Extract retrieved KC chunks from the workflow response for citations."""
    sources = []
    try:
        # Chunks live under output.new_messages, not result.new_messages
        output = result.get("output", result.get("result", {}))
        if not isinstance(output, dict):
            return sources
        messages = output.get("new_messages", [])
        for msg in messages:
            for part in msg.get("parts", []):
                if (
                    part.get("part_kind") == "tool-return"
                    and "Knowledge_Retrieval" in part.get("tool_name", "")
                ):
                    content = part.get("content", {})
                    if isinstance(content, str):
                        content = json.loads(content)
                    docs = content.get("result", {}).get("retrieved_documents", [])
                    for doc in docs:
                        meta = doc.get("metadata", {})
                        sources.append(
                            {
                                "source": meta.get("source", "Unknown"),
                                "page": meta.get("page_number"),
                                "text": doc.get("content", ""),
                                "score": round(doc.get("score", 0), 3),
                            }
                        )
    except (KeyError, TypeError, json.JSONDecodeError):
        pass
    return sources


@app.get("/api/health")
async def health():
    return {"status": "ok", "mode": "ai-studio"}


# --------------- Document / Blob endpoints ---------------

def _get_container_client() -> ContainerClient:
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container = os.getenv("AZURE_STORAGE_CONTAINER", "guideline-documents")
    if not conn_str:
        raise HTTPException(
            status_code=500,
            detail="AZURE_STORAGE_CONNECTION_STRING not configured in .env",
        )
    return ContainerClient.from_connection_string(conn_str, container_name=container)


@app.get("/api/documents")
async def list_documents():
    """List all PDF documents in the Azure Blob container."""
    client = _get_container_client()
    docs = []
    for blob in client.list_blobs():
        if blob.name.lower().endswith(".pdf"):
            docs.append(
                {
                    "name": blob.name,
                    "size": blob.size,
                    "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
                }
            )
    return docs


@app.get("/api/documents/{name:path}")
async def get_document(name: str):
    """Return a PDF document from Azure Blob storage."""
    name = unquote(name)
    client = _get_container_client()
    blob_client = client.get_blob_client(name)
    try:
        data = blob_client.download_blob().readall()
    except Exception:
        raise HTTPException(status_code=404, detail=f"Document not found: {name}")

    # Use ASCII-safe filename for Content-Disposition header
    safe_name = name.split("/")[-1].encode("ascii", "replace").decode("ascii")
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )
