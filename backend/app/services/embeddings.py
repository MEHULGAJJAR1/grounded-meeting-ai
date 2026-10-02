"""Portable vector storage. OpenAI embeddings or clearly identified local hashing.

The local path is a real deterministic lexical feature embedding, not a fake
OpenAI vector or a learned semantic model. Provider/model identities never mix.
"""

from collections import Counter
import hashlib
import math
import re

from openai import OpenAI

from app.config import get_settings

LOCAL_MODEL = "lexical-hash-v1-384"
STOPWORDS = set(
    "the a an is are was were to for of and or in on at by with it that this be we i you me my our all what which who how show find about discussed meeting meetings task tasks please".split()
)
SYNONYMS = {
    "deployment": "deploy",
    "deployed": "deploy",
    "deploying": "deploy",
    "release": "deploy",
    "authentication": "auth",
    "login": "auth",
    "sign-in": "auth",
    "decisions": "decision",
    "questions": "question",
    "risks": "risk",
    "blockers": "risk",
    "overdue": "overdue",
    "deadlines": "deadline",
}


def tokens(text: str) -> list[str]:
    return [
        SYNONYMS.get(word, word)
        for word in re.findall(r"[a-z0-9]+", text.casefold())
        if word not in STOPWORDS
    ]


def local_embedding(text: str) -> list[float]:
    terms = tokens(text)
    counts = Counter(terms + [f"{a}_{b}" for a, b in zip(terms, terms[1:])])
    vector = [0.0] * 384
    for word, frequency in counts.items():
        digest = hashlib.blake2b(word.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "little") % len(vector)
        sign = 1 if digest[4] & 1 else -1
        vector[index] += sign * (1 + math.log(frequency))
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def embed_texts(
    texts: list[str], provider: str | None = None, model: str | None = None
) -> tuple[list[list[float]], str, str]:
    settings = get_settings()
    provider = provider or settings.active_provider
    if provider == "local":
        return [local_embedding(text) for text in texts], "local", LOCAL_MODEL
    if not settings.openai_api_key:
        raise RuntimeError("An OpenAI key is needed to query this OpenAI embedding index")
    model = model or settings.openai_embedding_model
    client = OpenAI(
        api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds, max_retries=2
    )
    vectors = []
    for offset in range(0, len(texts), 32):
        response = client.embeddings.create(
            model=model, input=texts[offset : offset + 32], encoding_format="float"
        )
        batch = sorted(response.data, key=lambda value: value.index)
        expected = len(texts[offset : offset + 32])
        if len(batch) != expected or [item.index for item in batch] != list(range(expected)):
            raise RuntimeError("The embedding provider returned an incomplete or misindexed batch")
        for item in batch:
            if not item.embedding or any(not math.isfinite(value) for value in item.embedding):
                raise RuntimeError("The embedding provider returned an invalid vector")
            if vectors and len(item.embedding) != len(vectors[0]):
                raise RuntimeError("The embedding provider returned inconsistent vector dimensions")
            vectors.append(item.embedding)
    return vectors, "openai", model


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    norm = math.sqrt(sum(x * x for x in left) * sum(y * y for y in right))
    return sum(x * y for x, y in zip(left, right)) / norm if norm else 0.0
