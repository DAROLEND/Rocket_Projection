import chromadb
from sentence_transformers import SentenceTransformer

_embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
_chroma_client = chromadb.PersistentClient(path="./chroma_data")
_collection = _chroma_client.get_or_create_collection(name="simulations")


def build_description(simulation) -> str:
    return (
        f"Simulation #{simulation.id}: rocket with mass {simulation.mass}kg, "
        f"drag coefficient {simulation.drag_coefficient}, "
        f"cross-section area {simulation.cross_section_area}m², "
        f"launched at {simulation.angle_deg}° with initial velocity {simulation.v0}m/s. "
        f"Result: apogee {simulation.apogee}m, flight time {simulation.flight_time:.2f}s, "
        f"landed at distance {simulation.landing_x:.2f}m."
    )


def index_simulation(simulation) -> None:
    description = build_description(simulation)
    embedding = _embedding_model.encode(description).tolist()

    # upsert (not add) — editing an existing simulation re-indexes the same id
    # with a fresh description/embedding instead of erroring on a duplicate.
    _collection.upsert(
        ids=[str(simulation.id)],
        embeddings=[embedding],
        documents=[description],
        metadatas=[{"simulation_id": simulation.id}],
    )


def search_similar_with_ids(query: str, top_k: int = 3) -> list[tuple[int, str]]:
    query_embedding = _embedding_model.encode(query).tolist()
    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )
    if not results["documents"] or not results["documents"][0]:
        return []

    ids = [int(id_str) for id_str in results["ids"][0]]
    docs = results["documents"][0]
    return list(zip(ids, docs))

import instructor
from anthropic import Anthropic
from app.config import settings
from app.schemas import AskResponse

_claude_client = instructor.from_anthropic(Anthropic(api_key=settings.anthropic_api_key))


def answer_question(question: str) -> AskResponse:
    relevant_docs_with_ids = search_similar_with_ids(question, top_k=3)

    if not relevant_docs_with_ids:
        return AskResponse(
            answer="У мене ще немає жодних симуляцій для аналізу. Спочатку запусти хоча б одну через /simulate.",
            confidence="low",
            relevant_simulation_ids=[],
        )

    context = "\n".join(f"- {doc}" for _, doc in relevant_docs_with_ids)

    prompt = f"""You are a rocket trajectory analysis assistant. Answer the user's question
based ONLY on the simulation data provided below. Be concise and specific, referencing
actual numbers from the data.

Simulation data:
{context}

Question: {question}"""

    response = _claude_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
        response_model=AskResponse,
    )

    return response