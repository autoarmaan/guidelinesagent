import os

import chromadb
from chromadb.utils import embedding_functions

from document_loader import extract_sections_from_docx

COLLECTION_NAME = "guidelines"


def get_chroma_client():
    return chromadb.PersistentClient(path="./chroma_db")


def get_embedding_function(openai_api_key: str):
    return embedding_functions.OpenAIEmbeddingFunction(
        api_key=openai_api_key, model_name="text-embedding-3-small"
    )


def ingest_documents(documents_dir: str, openai_api_key: str) -> int:
    client = get_chroma_client()
    ef = get_embedding_function(openai_api_key)

    # Delete existing collection if it exists
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=ef
    )

    all_ids = []
    all_documents = []
    all_metadatas = []

    for filename in sorted(os.listdir(documents_dir)):
        if not filename.endswith(".docx") or filename.startswith("~$"):
            continue
        filepath = os.path.join(documents_dir, filename)
        sections = extract_sections_from_docx(filepath)
        for i, section in enumerate(sections):
            all_ids.append(f"{filename}_sec_{i}")
            all_documents.append(section["content"])
            all_metadatas.append({
                "source": section["source"],
                "title": section["title"],
                "path": section["path"],
                "level": section["level"],
            })

    if not all_ids:
        return 0

    collection.add(
        ids=all_ids,
        documents=all_documents,
        metadatas=all_metadatas,
    )
    return len(all_ids)


def query_documents(
    query: str, openai_api_key: str, n_results: int = 5
) -> list[dict]:
    """Returns list of {text, source, path, title} dicts."""
    client = get_chroma_client()
    ef = get_embedding_function(openai_api_key)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=ef
    )

    results = collection.query(query_texts=[query], n_results=n_results)

    if not results["documents"] or not results["documents"][0]:
        return []

    chunks = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        chunks.append({
            "text": doc,
            "source": meta.get("source", ""),
            "path": meta.get("path", ""),
            "title": meta.get("title", ""),
        })
    return chunks
