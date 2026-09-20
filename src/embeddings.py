from __future__ import annotations

import hashlib
import json
import math
import os
import urllib.request
from typing import Any, Callable

# Multilingual model suitable for the Vietnamese corpora used in this Lab.
# The local backend remains optional; required checkpoints use MockEmbedder.
LOCAL_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"
OPENROUTER_EMBEDDING_MODEL = "nvidia/nemotron-3-embed-1b:free"
OPENROUTER_EMBEDDING_URL = "https://openrouter.ai/api/v1/embeddings"
EMBEDDING_PROVIDER_ENV = "EMBEDDING_PROVIDER"


class MockEmbedder:
    """Deterministic embedding backend used by tests and default classroom runs."""

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim
        self._backend_name = "mock embeddings fallback"

    def __call__(self, text: str) -> list[float]:
        digest = hashlib.md5(text.encode()).hexdigest()
        seed = int(digest, 16)
        vector = []
        for _ in range(self.dim):
            seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
            vector.append((seed / 0xFFFFFFFF) * 2 - 1)
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class LocalEmbedder:
    """Sentence Transformers-backed local embedder."""

    def __init__(self, model_name: str = LOCAL_EMBEDDING_MODEL) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._backend_name = model_name
        self.model = SentenceTransformer(model_name)

    def __call__(self, text: str) -> list[float]:
        embedding = self.model.encode(text, normalize_embeddings=True)
        if hasattr(embedding, "tolist"):
            return embedding.tolist()
        return [float(value) for value in embedding]


class OpenAIEmbedder:
    """OpenAI embeddings API-backed embedder."""

    def __init__(self, model_name: str = OPENAI_EMBEDDING_MODEL) -> None:
        from openai import OpenAI

        self.model_name = model_name
        self._backend_name = model_name
        self.client = OpenAI()

    def __call__(self, text: str) -> list[float]:
        response = self.client.embeddings.create(model=self.model_name, input=text)
        return [float(value) for value in response.data[0].embedding]


class GeminiEmbedder:
    """Google Gemini embeddings API-backed embedder (google-genai SDK).

    Free-tier alternative to OpenAI for students without an OpenAI key —
    a Gemini API key (aistudio.google.com) has a free quota, no billing card needed.
    """

    def __init__(self, model_name: str = GEMINI_EMBEDDING_MODEL) -> None:
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) is required for GeminiEmbedder")
        self.model_name = model_name
        self._backend_name = model_name
        self.client = genai.Client(api_key=api_key)

    def __call__(self, text: str) -> list[float]:
        response = self.client.models.embed_content(model=self.model_name, contents=text)
        return [float(value) for value in response.embeddings[0].values]


def _openrouter_transport(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class OpenRouterEmbedder:
    """OpenRouter embeddings client with batching and an in-process cache."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout: float = 60.0,
        transport: Callable[
            [str, dict[str, str], dict[str, Any], float], dict[str, Any]
        ] = _openrouter_transport,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self._api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required for OpenRouterEmbedder")
        self.model_name = (
            model_name
            or os.getenv("OPENROUTER_EMBEDDING_MODEL")
            or OPENROUTER_EMBEDDING_MODEL
        )
        self.timeout = timeout
        self._transport = transport
        self._backend_name = self.model_name
        self._cache: dict[tuple[str, str], list[float]] = {}

    def _embed_many(self, texts: list[str], input_type: str) -> list[list[float]]:
        if not texts:
            return []

        missing = list(
            dict.fromkeys(
                text for text in texts if (input_type, text) not in self._cache
            )
        )
        if missing:
            payload = {
                "model": self.model_name,
                "input": missing,
                "encoding_format": "float",
                "input_type": input_type,
            }
            response = self._transport(
                OPENROUTER_EMBEDDING_URL,
                {
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                payload,
                self.timeout,
            )
            data = sorted(response.get("data", []), key=lambda item: item["index"])
            if len(data) != len(missing):
                raise RuntimeError(
                    "OpenRouter returned an unexpected number of embeddings"
                )
            for text, item in zip(missing, data):
                self._cache[(input_type, text)] = [
                    float(value) for value in item["embedding"]
                ]

        return [list(self._cache[(input_type, text)]) for text in texts]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed_many(texts, "search_document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed_many([text], "search_query")[0]

    def __call__(self, text: str) -> list[float]:
        return self.embed_query(text)


_mock_embed = MockEmbedder()
