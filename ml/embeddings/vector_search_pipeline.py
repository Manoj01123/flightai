"""
Vertex AI Vector Search embedding pipeline for RAG.

Embeds historical fare Q&A pairs using Gemini text-embedding-004, then:
  1. Writes JSONL embeddings to GCS
  2. Creates / updates a Vertex AI Vector Search index
  3. Deploys the index to an IndexEndpoint for real-time similarity search

The orchestrator agent calls the deployed endpoint to answer:
  "What does a flight from JFK→LAX usually cost in July?"
by finding the top-k nearest historical data points.

Usage:
    python -m ml.embeddings.vector_search_pipeline --action build   # full build
    python -m ml.embeddings.vector_search_pipeline --action query --text "cheap flights JFK LAX"
"""
from __future__ import annotations

import argparse
import json
import uuid
from datetime import date
from pathlib import Path
from typing import List, Dict

PROJECT = "flightai-dev"
REGION = "us-central1"
GCS_BUCKET = "flightai-models"
EMBEDDING_MODEL = "text-embedding-004"
INDEX_DISPLAY_NAME = "flightai-fare-rag-index"
ENDPOINT_DISPLAY_NAME = "flightai-fare-rag-endpoint"
DIMENSIONS = 768  # text-embedding-004 output size


# ── Document corpus ───────────────────────────────────────────────────────────

def build_corpus() -> list[dict]:
    """
    Build the document corpus that will be embedded.
    Each doc is a natural-language description of a route + fare pattern
    derived from the synthetic/historical data.
    """
    route_patterns = [
        ("JFK", "LAX", 280, "New York to Los Angeles"),
        ("LAX", "JFK", 280, "Los Angeles to New York"),
        ("ORD", "LAX", 240, "Chicago to Los Angeles"),
        ("JFK", "MIA", 180, "New York to Miami"),
        ("LAX", "SFO", 120, "Los Angeles to San Francisco"),
        ("ORD", "DFW", 160, "Chicago to Dallas"),
        ("ATL", "LAX", 260, "Atlanta to Los Angeles"),
        ("JFK", "ORD", 170, "New York to Chicago"),
        ("DFW", "LAX", 220, "Dallas to Los Angeles"),
        ("SEA", "LAX", 150, "Seattle to Los Angeles"),
        ("BOS", "LAX", 290, "Boston to Los Angeles"),
        ("LAX", "LAS", 90, "Los Angeles to Las Vegas"),
        ("JFK", "SFO", 310, "New York to San Francisco"),
        ("ORD", "MIA", 200, "Chicago to Miami"),
        ("ATL", "JFK", 190, "Atlanta to New York"),
        ("DEN", "LAX", 180, "Denver to Los Angeles"),
        ("PHX", "LAX", 110, "Phoenix to Los Angeles"),
        ("MIA", "JFK", 185, "Miami to New York"),
        ("SFO", "SEA", 130, "San Francisco to Seattle"),
        ("JFK", "BOS", 95, "New York to Boston"),
    ]

    months = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December",
    }
    month_mult = {
        1: 0.90, 2: 0.88, 3: 1.05, 4: 1.08, 5: 1.10, 6: 1.20,
        7: 1.22, 8: 1.18, 9: 0.95, 10: 1.00, 11: 1.15, 12: 1.25,
    }

    docs = []
    for origin, dest, baseline, route_name in route_patterns:
        # One doc per route summarizing annual pattern
        annual = {m: round(baseline * mult, 0) for m, mult in month_mult.items()}
        cheapest_month = min(annual, key=annual.get)
        priciest_month = max(annual, key=annual.get)

        doc_text = (
            f"Flight route {origin} to {dest} ({route_name}). "
            f"Average base price: ${baseline}. "
            f"Cheapest month: {months[cheapest_month]} (~${annual[cheapest_month]:.0f}). "
            f"Most expensive month: {months[priciest_month]} (~${annual[priciest_month]:.0f}). "
            f"Book 30+ days ahead for best prices. "
            f"Last-minute (under 7 days) fares run 35–55% above average. "
            f"Friday and Sunday departures cost ~10–18% more; Tuesday and Wednesday are cheapest."
        )

        docs.append({
            "id": f"{origin}-{dest}-annual",
            "text": doc_text,
            "metadata": {"origin": origin, "destination": dest, "baseline": baseline},
        })

        # Also add per-month docs for fine-grained retrieval
        for m, price in annual.items():
            docs.append({
                "id": f"{origin}-{dest}-{m:02d}",
                "text": (
                    f"Flight {origin} to {dest} in {months[m]}: "
                    f"typical price around ${price:.0f}. "
                    f"{'Peak season — prices elevated.' if month_mult[m] >= 1.15 else ''}"
                    f"{'Off-peak — good deals available.' if month_mult[m] <= 0.90 else ''}"
                ),
                "metadata": {"origin": origin, "destination": dest, "month": m},
            })

    return docs


# ── Embedding ─────────────────────────────────────────────────────────────────

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Call Gemini text-embedding-004 via Vertex AI SDK in batches of 250."""
    from vertexai.language_models import TextEmbeddingModel
    import vertexai

    vertexai.init(project=PROJECT, location=REGION)
    model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)

    all_embeddings: list[list[float]] = []
    batch_size = 250
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        results = model.get_embeddings(batch)
        all_embeddings.extend([r.values for r in results])
        print(f"  Embedded {min(i + batch_size, len(texts))}/{len(texts)}")

    return all_embeddings


# ── GCS upload ────────────────────────────────────────────────────────────────

def upload_embeddings_to_gcs(docs: list[dict], embeddings: list[list[float]]) -> str:
    """Write JSONL format expected by Vertex AI Vector Search."""
    from google.cloud import storage

    jsonl_lines = []
    for doc, vec in zip(docs, embeddings):
        jsonl_lines.append(json.dumps({
            "id": doc["id"],
            "embedding": vec,
        }))

    content = "\n".join(jsonl_lines)
    gcs_path = f"vector-search/fare_embeddings_{date.today().isoformat()}.json"

    client = storage.Client(project=PROJECT)
    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(gcs_path)
    blob.upload_from_string(content, content_type="application/jsonl")

    full_path = f"gs://{GCS_BUCKET}/{gcs_path}"
    print(f"Embeddings uploaded → {full_path}  ({len(jsonl_lines)} vectors)")
    return full_path


# ── Vertex AI Index ───────────────────────────────────────────────────────────

def create_or_update_index(gcs_jsonl_path: str) -> str:
    """Create the Vertex AI Vector Search index (or update if it already exists)."""
    from google.cloud import aiplatform

    aiplatform.init(project=PROJECT, location=REGION)

    # Check if index already exists
    existing = [
        idx for idx in aiplatform.MatchingEngineIndex.list()
        if idx.display_name == INDEX_DISPLAY_NAME
    ]

    gcs_folder = gcs_jsonl_path.rsplit("/", 1)[0]  # strip filename

    if existing:
        index = existing[0]
        print(f"Updating existing index: {index.resource_name}")
        index.update_embeddings(contents_delta_uri=gcs_folder)
    else:
        print(f"Creating new index: {INDEX_DISPLAY_NAME}")
        index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
            display_name=INDEX_DISPLAY_NAME,
            contents_delta_uri=gcs_folder,
            dimensions=DIMENSIONS,
            approximate_neighbors_count=10,
            distance_measure_type="DOT_PRODUCT_DISTANCE",
            description="FlightAI fare RAG embeddings (text-embedding-004)",
        )

    print(f"Index ready: {index.resource_name}")
    return index.resource_name


def deploy_index(index_resource_name: str) -> str:
    """Deploy the index to an IndexEndpoint for online queries."""
    from google.cloud import aiplatform

    aiplatform.init(project=PROJECT, location=REGION)

    # Get or create endpoint
    existing_eps = [
        ep for ep in aiplatform.MatchingEngineIndexEndpoint.list()
        if ep.display_name == ENDPOINT_DISPLAY_NAME
    ]

    if existing_eps:
        endpoint = existing_eps[0]
        print(f"Using existing endpoint: {endpoint.resource_name}")
    else:
        print(f"Creating endpoint: {ENDPOINT_DISPLAY_NAME}")
        endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
            display_name=ENDPOINT_DISPLAY_NAME,
            public_endpoint_enabled=True,
        )

    index = aiplatform.MatchingEngineIndex(index_resource_name)
    deployed_index_id = INDEX_DISPLAY_NAME.replace("-", "_")

    # Check if already deployed
    already_deployed = any(
        d.id == deployed_index_id for d in endpoint.deployed_indexes
    )
    if not already_deployed:
        endpoint.deploy_index(
            index=index,
            deployed_index_id=deployed_index_id,
            display_name=INDEX_DISPLAY_NAME,
            min_replica_count=1,
            max_replica_count=2,
        )
        print(f"Index deployed to endpoint: {endpoint.resource_name}")

    return endpoint.resource_name


# ── Query ─────────────────────────────────────────────────────────────────────

def query_index(query_text: str, top_k: int = 5) -> list[dict]:
    """
    Find the top-k most relevant fare corpus entries for a natural-language query.
    Used by the orchestrator's RAG node.
    """
    from google.cloud import aiplatform
    import vertexai
    from vertexai.language_models import TextEmbeddingModel

    vertexai.init(project=PROJECT, location=REGION)
    aiplatform.init(project=PROJECT, location=REGION)

    # Embed the query
    embed_model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)
    [query_embedding] = embed_model.get_embeddings([query_text])

    # Find endpoint
    endpoints = [
        ep for ep in aiplatform.MatchingEngineIndexEndpoint.list()
        if ep.display_name == ENDPOINT_DISPLAY_NAME
    ]
    if not endpoints:
        raise RuntimeError(f"Endpoint '{ENDPOINT_DISPLAY_NAME}' not found. Run --action build first.")

    endpoint = endpoints[0]
    deployed_index_id = INDEX_DISPLAY_NAME.replace("-", "_")

    results = endpoint.find_neighbors(
        deployed_index_id=deployed_index_id,
        queries=[query_embedding.values],
        num_neighbors=top_k,
    )

    matches = []
    for match in results[0]:
        matches.append({"id": match.id, "distance": match.distance})

    return matches


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vertex AI Vector Search pipeline for FlightAI RAG")
    parser.add_argument("--action", choices=["build", "query"], default="build")
    parser.add_argument("--text", help="Query text (for --action query)")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    if args.action == "build":
        print("Building corpus...")
        docs = build_corpus()
        print(f"  {len(docs)} documents")

        print("Embedding corpus with Gemini text-embedding-004...")
        embeddings = embed_texts([d["text"] for d in docs])

        print("Uploading to GCS...")
        gcs_path = upload_embeddings_to_gcs(docs, embeddings)

        print("Creating/updating Vertex AI Vector Search index...")
        index_name = create_or_update_index(gcs_path)

        print("Deploying index to endpoint...")
        endpoint_name = deploy_index(index_name)

        print(f"\nDone!")
        print(f"  Index:    {index_name}")
        print(f"  Endpoint: {endpoint_name}")
        print(f"  Docs:     {len(docs)}")

    elif args.action == "query":
        if not args.text:
            parser.error("--text is required for --action query")
        results = query_index(args.text, top_k=args.top_k)
        print(f"Top {args.top_k} matches for: '{args.text}'")
        for r in results:
            print(f"  {r['id']}  (distance={r['distance']:.4f})")
