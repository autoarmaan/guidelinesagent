"""
Local document parsing + AI Studio vector store ingestion.

Parses .docx files using the section-aware parser (extract_sections_from_docx),
then sends chunks to AI Studio's "Embed and Store Chunks" workflow for
embedding and vector storage.

Usage:
    python ingest_to_studio.py                          # Ingest all docs in documents/
    python ingest_to_studio.py path/to/file.docx        # Ingest a single file
"""

import json
import os
import subprocess
import sys

# Add parent dir so we can import document_loader
sys.path.insert(0, os.path.dirname(__file__))
from document_loader import extract_sections_from_docx

WORKFLOW_ID = "a8f5f8b1-5949-4218-acb3-4c01eca05263"
COLLECTION_NAME = "company-guidelines"
DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "documents")


def sections_to_chunks(sections: list[dict]) -> list[str]:
    """Convert structured sections into chunk strings with section path context."""
    chunks = []
    for section in sections:
        path = section["path"]
        content = section["content"]
        source = section["source"]
        # Prefix each chunk with its section path for better retrieval + citation
        chunk_text = f"[{source}] {path}\n\n{content}"
        chunks.append(chunk_text)
    return chunks


def ingest_file(file_path: str):
    """Parse a single docx and send chunks to AI Studio."""
    filename = os.path.basename(file_path)
    print(f"Parsing: {filename}")

    sections = extract_sections_from_docx(file_path)
    print(f"  Found {len(sections)} sections")

    chunks = sections_to_chunks(sections)
    print(f"  Created {len(chunks)} chunks")

    if not chunks:
        print("  No chunks to ingest, skipping.")
        return

    # Build input for the workflow
    workflow_input = {
        "chunks": chunks,
        "source": filename,
        "collection_name": COLLECTION_NAME,
        "metadata": {
            "source_file": filename,
            "total_sections": len(sections),
        },
    }

    input_json = json.dumps(workflow_input)

    print(f"  Sending {len(chunks)} chunks to AI Studio workflow...")

    result = subprocess.run(
        [
            "autonomize", "run", WORKFLOW_ID,
            "--input", input_json,
            "--no-stream",
        ],
        capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )

    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""

    print(stdout)
    if stderr:
        print(stderr)

    if result.returncode == 0 and "completed" in stdout.lower():
        print(f"  Successfully ingested {filename}")
    else:
        print(f"  Warning: ingestion may have failed for {filename}")


def ingest_directory(directory: str):
    """Ingest all .docx files from a directory."""
    docx_files = sorted(
        f for f in os.listdir(directory) if f.endswith(".docx")
    )

    if not docx_files:
        print(f"No .docx files found in {directory}")
        return

    print(f"Found {len(docx_files)} document(s) to ingest\n")

    for filename in docx_files:
        filepath = os.path.join(directory, filename)
        ingest_file(filepath)
        print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Ingest a specific file
        ingest_file(sys.argv[1])
    else:
        # Ingest all docs from documents/ directory
        ingest_directory(DOCUMENTS_DIR)
