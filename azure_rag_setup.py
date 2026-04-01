"""
Azure AI Search - RAG Index Setup Automation
============================================
Automates the full pipeline:
  1. Load knowledge base from commerce_knowledge_base.json
  2. Create Azure AI Search index with semantic search config
  3. Prepare and upload documents to the index
  4. Verify indexing with test queries

Requirements:
    pip install azure-search-documents azure-core openai python-dotenv tqdm

Usage:
    1. Fill in your credentials in .env
    2. Edit commerce_knowledge_base.json to customise knowledge base
    3. Run: python azure_rag_setup.py
"""

import os
import json
import time
import uuid
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from tqdm import tqdm

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceExistsError, HttpResponseError
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    SemanticSearch,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
)
from azure.search.documents.models import QueryType

# ── Optional: embeddings via Azure OpenAI ─────────────────────────────────
try:
    from openai import AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

load_dotenv()


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION — edit values in your .env file
# ══════════════════════════════════════════════════════════════════════════════

AZURE_SEARCH_ENDPOINT  = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
INDEX_NAME             = os.getenv("INDEX_NAME", "commerce-schema-index")

# Optional — only needed for vector/embedding search
AZURE_OPENAI_ENDPOINT  = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY       = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_API_VER   = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
EMBEDDING_DEPLOYMENT   = os.getenv("EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
EMBEDDING_DIMENSIONS   = 1536

USE_VECTOR_SEARCH      = bool(AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY and OPENAI_AVAILABLE)

# ── File paths ────────────────────────────────────────────────────────────
KNOWLEDGE_BASE_FILE    = Path("commerce_knowledge_base.json")   # ← main knowledge base
KNOWLEDGE_BASE_DIR     = Path("knowledge_base")                 # ← optional extra files folder


# ══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE LOADER
# Reads from commerce_knowledge_base.json — edit that file, not this one
# ══════════════════════════════════════════════════════════════════════════════

def load_knowledge_base() -> list[dict]:
    """
    Load all entries from commerce_knowledge_base.json.
    To add/edit/remove entries, open commerce_knowledge_base.json directly.
    No changes needed in this Python file.
    """
    if not KNOWLEDGE_BASE_FILE.exists():
        raise FileNotFoundError(
            f"\n  ✗ Knowledge base file not found: {KNOWLEDGE_BASE_FILE}\n"
            "  Make sure commerce_knowledge_base.json is in the same folder as this script."
        )

    with open(KNOWLEDGE_BASE_FILE, encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("entries", [])
    meta    = data.get("metadata", {})

    log.info(
        "Loaded %d entries from %s  [version: %s]",
        len(entries),
        KNOWLEDGE_BASE_FILE.name,
        meta.get("version", "unknown"),
    )
    return entries


def load_extra_documents(directory: Path) -> list[dict]:
    """
    Optionally load supplemental entries from /knowledge_base folder.
    Supports .json (list of dicts) and .txt (one entry per paragraph).
    These are merged on top of the main knowledge base file.
    """
    docs = []
    if not directory.exists():
        return docs

    for file in directory.iterdir():
        if file.suffix == ".json":
            try:
                with open(file, encoding="utf-8") as f:
                    raw = json.load(f)
                items = raw if isinstance(raw, list) else raw.get("entries", [])
                docs.extend(items)
                log.info("  Extra: loaded %d entries from %s", len(items), file.name)
            except Exception as exc:
                log.warning("  Skipping %s: %s", file.name, exc)

        elif file.suffix == ".txt":
            with open(file, encoding="utf-8") as f:
                paragraphs = [p.strip() for p in f.read().split("\n\n") if p.strip()]
            for i, para in enumerate(paragraphs):
                docs.append({
                    "field_name":               f"{file.stem}_entry_{i}",
                    "domain":                   "commerce",
                    "sub_domain":               "general",
                    "data_type":                "",
                    "constraints":              "",
                    "professional_description": para,
                    "examples":                 "",
                    "related_fields":           "",
                    "compliance_notes":         "",
                })
            log.info("  Extra: loaded %d paragraphs from %s", len(paragraphs), file.name)

    return docs


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _validate_env() -> None:
    missing = [v for v in ("AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_ADMIN_KEY") if not os.getenv(v)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in your credentials."
        )


def _get_embedding(text: str, client: "AzureOpenAI") -> list[float]:
    response = client.embeddings.create(input=text, model=EMBEDDING_DEPLOYMENT)
    return response.data[0].embedding


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — CREATE INDEX
# ══════════════════════════════════════════════════════════════════════════════

def create_index(index_client: SearchIndexClient) -> None:
    """
    Create the Azure AI Search index with semantic search configuration.
    Automatically deletes and recreates if the index already exists.
    """
    log.info("━━ Step 1: Creating index '%s' ━━", INDEX_NAME)

    fields = [
        SimpleField(name="id",                          type=SearchFieldDataType.String, key=True, filterable=True),
        SearchableField(name="field_name",              type=SearchFieldDataType.String, filterable=True, sortable=True),
        SimpleField(name="domain",                      type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="sub_domain",                  type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchableField(name="professional_description",type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
        SimpleField(name="data_type",                   type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="constraints",             type=SearchFieldDataType.String),
        SearchableField(name="examples",                type=SearchFieldDataType.String),
        SearchableField(name="related_fields",          type=SearchFieldDataType.String),
        SearchableField(name="compliance_notes",        type=SearchFieldDataType.String),
    ]

    # ── Vector field — only added when Azure OpenAI is configured ──────────
    vector_search = None
    if USE_VECTOR_SEARCH:
        fields.append(
            SearchField(
                name="description_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=EMBEDDING_DIMENSIONS,
                vector_search_profile_name="hnsw-profile",
            )
        )
        vector_search = VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw-algo")],
            profiles=[VectorSearchProfile(name="hnsw-profile", algorithm_configuration_name="hnsw-algo")],
        )
        log.info("  Vector search enabled (dimensions=%d)", EMBEDDING_DIMENSIONS)

    # ── Semantic configuration ─────────────────────────────────────────────
    semantic_config = SemanticConfiguration(
        name="commerce-semantic",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="field_name"),
            content_fields=[SemanticField(field_name="professional_description")],
            keywords_fields=[
                SemanticField(field_name="domain"),
                SemanticField(field_name="sub_domain"),
                SemanticField(field_name="constraints"),
            ],
        ),
    )

    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        semantic_search=SemanticSearch(configurations=[semantic_config]),
        vector_search=vector_search,
    )

    try:
        index_client.create_index(index)
        log.info("  ✓ Index created successfully")
    except (ResourceExistsError, HttpResponseError) as exc:
        # Azure throws HttpResponseError with code ResourceNameAlreadyInUse
        # when the index already exists — handle both cases the same way
        already_exists = isinstance(exc, ResourceExistsError) or (
            isinstance(exc, HttpResponseError) and
            "ResourceNameAlreadyInUse" in str(exc)
        )
        if already_exists:
            log.warning("  ⚠  Index already exists — deleting and recreating")
            try:
                index_client.delete_index(INDEX_NAME)
                log.info("  ✓ Old index deleted")
            except Exception as del_exc:
                log.error("  ✗ Failed to delete existing index: %s", del_exc)
                raise
            time.sleep(3)   # give Azure time to fully remove it
            index_client.create_index(index)
            log.info("  ✓ Index recreated successfully")
        else:
            log.error("  ✗ Failed to create index: %s", exc)
            raise


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — PREPARE DOCUMENTS
# ══════════════════════════════════════════════════════════════════════════════

def prepare_documents(
    raw_docs: list[dict],
    openai_client: Optional["AzureOpenAI"] = None,
) -> list[dict]:
    """
    Assign unique IDs and optionally generate embedding vectors
    for each knowledge base entry before uploading.
    """
    log.info("━━ Step 2: Preparing %d documents ━━", len(raw_docs))
    prepared = []

    for doc in tqdm(raw_docs, desc="  Preparing", unit="doc"):
        entry = {
            "id":                       str(uuid.uuid4()),
            "field_name":               doc.get("field_name", ""),
            "domain":                   doc.get("domain", "commerce"),
            "sub_domain":               doc.get("sub_domain", "general"),
            "professional_description": doc.get("professional_description", ""),
            "data_type":                doc.get("data_type", ""),
            "constraints":              doc.get("constraints", ""),
            "examples":                 doc.get("examples", ""),
            "related_fields":           doc.get("related_fields", ""),
            "compliance_notes":         doc.get("compliance_notes", ""),
        }

        if USE_VECTOR_SEARCH and openai_client:
            embed_text = (
                f"{entry['field_name']} {entry['professional_description']} "
                f"{entry['constraints']} {entry['related_fields']}"
            )
            try:
                entry["description_vector"] = _get_embedding(embed_text, openai_client)
            except Exception as exc:
                log.warning("  Embedding failed for '%s': %s", entry["field_name"], exc)

        prepared.append(entry)

    log.info("  ✓ %d documents prepared", len(prepared))
    return prepared


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — UPLOAD DOCUMENTS
# ══════════════════════════════════════════════════════════════════════════════

def upload_documents(search_client: SearchClient, documents: list[dict], batch_size: int = 5) -> None:
    """
    Upload documents in small batches with retry logic.
    Batch size is kept at 5 because each document contains a 1536-dim
    embedding vector (~35KB per doc). Sending 50 at once produces a 900KB+
    payload that Azure forcibly closes (ConnectionResetError 10054).
    """
    log.info("Step 3: Uploading %d documents (batch_size=%d)", len(documents), batch_size)
    total_uploaded = 0
    total_batches  = (len(documents) + batch_size - 1) // batch_size

    for i in range(0, len(documents), batch_size):
        batch     = documents[i : i + batch_size]
        batch_num = i // batch_size + 1
        attempt   = 0

        while attempt < 3:
            try:
                result = search_client.upload_documents(documents=batch)
                failed = [r for r in result if not r.succeeded]
                if failed:
                    log.warning("  %d docs failed in batch %d/%d", len(failed), batch_num, total_batches)
                    for f in failed:
                        log.warning("    key=%s  error=%s", f.key, f.error_message)
                total_uploaded += len(batch) - len(failed)
                log.info("  Batch %d/%d done (%d docs)", batch_num, total_batches, len(batch) - len(failed))
                break

            except Exception as exc:
                attempt += 1
                wait = 2 ** attempt
                log.warning(
                    "  Batch %d/%d failed (attempt %d/3) retrying in %ds: %s",
                    batch_num, total_batches, attempt, wait, exc,
                )
                time.sleep(wait)

        time.sleep(0.5)   # small pause between batches

    log.info("  Uploaded %d / %d documents successfully", total_uploaded, len(documents))


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — VERIFY INDEX
# ══════════════════════════════════════════════════════════════════════════════

def verify_index(search_client: SearchClient) -> None:
    """
    Run test semantic queries to confirm the index is populated and working.
    """
    log.info("━━ Step 4: Verifying index ━━")

    test_queries = [
        "customer email unique identifier",
        "order total payment amount",
        "stock quantity inventory warehouse",
    ]

    for query_text in test_queries:
        try:
            results = list(search_client.search(
                search_text=query_text,
                query_type=QueryType.SEMANTIC,
                semantic_configuration_name="commerce-semantic",
                top=1,
                select=["field_name", "domain", "professional_description"],
            ))

            if results:
                top     = results[0]
                snippet = top["professional_description"][:80] + "..."
                log.info(
                    "  ✓ %-42s → %-25s %s",
                    f"'{query_text}'",
                    f"{top['field_name']} [{top['domain']}]",
                    snippet,
                )
            else:
                log.warning("  ⚠  No results for: '%s'", query_text)

        except Exception as exc:
            log.warning("  ⚠  Verification query failed: %s", exc)

    log.info("  ✓ Verification complete")


# ══════════════════════════════════════════════════════════════════════════════
# RAG QUERY FUNCTION — called by your DDL generator per column
# ══════════════════════════════════════════════════════════════════════════════

def retrieve_context_for_column(
    field_name: str,
    table_name: str,
    search_client: SearchClient,
    top_k: int = 3,
) -> str:
    """
    Retrieve the most relevant professional descriptions from the index
    for a given column + table name.

    Returns a formatted context string ready to inject into a GPT prompt.

    Usage in your DDL generator:
        context = retrieve_context_for_column("customer_email", "customers", search_client)
    """
    results = list(search_client.search(
        search_text=f"{field_name} {table_name}",
        query_type=QueryType.SEMANTIC,
        semantic_configuration_name="commerce-semantic",
        top=top_k,
        select=[
            "field_name", "professional_description",
            "constraints", "related_fields",
            "compliance_notes", "domain", "sub_domain",
        ],
    ))

    if not results:
        return ""

    parts = []
    for r in results:
        part = (
            f"Reference Field : {r['field_name']} [{r['sub_domain']}]\n"
            f"Description     : {r['professional_description']}\n"
            f"Constraints     : {r['constraints']}\n"
            f"Related Fields  : {r['related_fields']}"
        )
        if r.get("compliance_notes"):
            part += f"\nCompliance      : {r['compliance_notes']}"
        parts.append(part)

    return "\n\n---\n\n".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print("\n" + "═" * 60)
    print("  Azure AI Search — Commerce RAG Index Setup")
    print("═" * 60 + "\n")

    _validate_env()

    credential    = AzureKeyCredential(AZURE_SEARCH_ADMIN_KEY)
    index_client  = SearchIndexClient(endpoint=AZURE_SEARCH_ENDPOINT, credential=credential)
    search_client = SearchClient(endpoint=AZURE_SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=credential)

    openai_client = None
    if USE_VECTOR_SEARCH:
        openai_client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_KEY,
            api_version=AZURE_OPENAI_API_VER,
        )
        log.info("Azure OpenAI client initialised for embeddings")

    # ── Load knowledge base entirely from JSON file ───────────────────────
    kb_entries = load_knowledge_base()
    extra_docs = load_extra_documents(KNOWLEDGE_BASE_DIR)
    all_docs   = kb_entries + extra_docs

    log.info(
        "Total entries: %d  (%d from %s + %d extra)",
        len(all_docs), len(kb_entries), KNOWLEDGE_BASE_FILE.name, len(extra_docs),
    )

    # ── Run pipeline ──────────────────────────────────────────────────────
    create_index(index_client)
    time.sleep(2)

    documents = prepare_documents(all_docs, openai_client)
    upload_documents(search_client, documents)
    time.sleep(3)

    verify_index(search_client)

    print("\n" + "═" * 60)
    print("  ✅  Setup complete!")
    print(f"  Index  : {INDEX_NAME}")
    print(f"  Docs   : {len(documents)} entries indexed")
    print(f"  Source : {KNOWLEDGE_BASE_FILE.name}")
    print(f"  Vector : {'enabled' if USE_VECTOR_SEARCH else 'disabled (set AZURE_OPENAI_* to enable)'}")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()