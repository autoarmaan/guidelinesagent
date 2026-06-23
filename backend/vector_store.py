import chromadb
from chromadb.utils import embedding_functions

from document_loader import load_documents

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

    docs = load_documents(documents_dir)
    if not docs:
        return 0

    collection.add(
        ids=[d["id"] for d in docs],
        documents=[d["text"] for d in docs],
        metadatas=[d["metadata"] for d in docs],
    )
    return len(docs)


def query_documents(query: str, openai_api_key: str, n_results: int = 5) -> list[str]:
    client = get_chroma_client()
    ef = get_embedding_function(openai_api_key)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=ef
    )

    results = collection.query(query_texts=[query], n_results=n_results)
    return results["documents"][0] if results["documents"] else []
