from functools import lru_cache
from sentence_transformers import SentenceTransformer
from app.config import load_settings


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    settings = load_settings()
    return SentenceTransformer(settings.embeddings.model)


def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors = _model().encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
