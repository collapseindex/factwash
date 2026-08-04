"""Integration test against the REAL mem0 Memory pipeline.

Only the two network boundaries are stubbed (the extraction LLM and the embedder); mem0's
own add/delete code, config validation, and vector store all run for real.

SCOPE, stated plainly: these tests do NOT re-establish that mem0 launders hearsay. That
result needs a live extraction LLM and belongs to the paper (Manufactured Confidence,
Table 1, 100% de-hedging). Here the extractor is stubbed to emit the laundered string the
paper observed, and what is under test is Factwash's half: that the gate fires on it and
that eviction and re-add work against real mem0 code paths and a real vector store.

Opt-in (Law #4: nothing that touches the network runs by default):

    FACTWASH_TEST_MEM0=1 pytest tests/test_integration/test_mem0_real.py

mem0 fetches tokenizer assets from HuggingFace on first construction, which is why this is
not part of the default suite.
"""
from __future__ import annotations

import hashlib
import json
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("FACTWASH_TEST_MEM0") != "1",
    reason="opt-in: set FACTWASH_TEST_MEM0=1 (constructing mem0 downloads tokenizer assets)",
)

pytest.importorskip("mem0", reason="mem0 not installed")

from mem0.embeddings.base import EmbeddingBase  # noqa: E402
from mem0.llms.base import LLMBase  # noqa: E402

import factwash  # noqa: E402

DIMS = 128
LAUNDERED = "Alice's clearance: admin"          # what mem0's extractor produces from hearsay
RUMOR = "Rumor has it Alice now has admin access after the reorg."
CLEAN_SOURCE = "I prefer dark mode in all my editors."
CLEAN_EXTRACTION = "User prefers dark mode in all editors."


class StubEmbedder(EmbeddingBase):
    """Deterministic hash embedding: no network, stable across runs."""

    def __init__(self, config=None):
        self.config = config

    def embed(self, text, memory_action=None):
        digest = hashlib.sha256((text or "").encode()).digest()
        return [digest[i % len(digest)] / 255.0 for i in range(DIMS)]

    def embed_batch(self, texts, memory_action=None):
        return [self.embed(t, memory_action) for t in texts]


class StubExtractor(LLMBase):
    """Stands in for mem0's consolidation LLM, emitting its ADDITIVE_EXTRACTION_PROMPT schema."""

    text = LAUNDERED

    def __init__(self, config=None):
        self.config = config

    def generate_response(self, messages, response_format=None, tools=None, **kwargs):
        return json.dumps({"memory": [{"id": "0", "text": type(self).text, "attributed_to": "user"}]})


@pytest.fixture
def mem0_client(tmp_path, monkeypatch):
    """Real mem0.Memory with only the LLM and embedder swapped out.

    Provider names stay 'openai' because mem0's pydantic config allowlists them; the factory
    maps are what actually decide which class is constructed.
    """
    from mem0.utils.factory import EmbedderFactory, LlmFactory

    mod = __name__
    monkeypatch.setitem(EmbedderFactory.provider_to_class, "openai", f"{mod}.StubEmbedder")
    monkeypatch.setitem(LlmFactory.provider_to_class, "openai",
                        (f"{mod}.StubExtractor", LlmFactory.provider_to_class["openai"][1]))
    monkeypatch.setattr(StubExtractor, "text", LAUNDERED, raising=False)

    from mem0 import Memory
    return Memory.from_config({
        "llm": {"provider": "openai", "config": {"model": "stub"}},
        "embedder": {"provider": "openai", "config": {"model": "stub", "embedding_dims": DIMS}},
        "vector_store": {"provider": "qdrant",
                         "config": {"collection_name": "factwash_test",
                                    "embedding_model_dims": DIMS, "path": str(tmp_path / "qdrant")}},
    })


def _stored(client, user_id="u1"):
    got = client.get_all(filters={"user_id": user_id})
    results = got.get("results", got) if isinstance(got, dict) else got
    return [r.get("memory", "") for r in results]


def test_real_mem0_launders_hearsay_and_factwash_evicts_it(mem0_client):
    # 1. naked mem0: the hedge and the attribution are gone, stored as settled fact
    naked = mem0_client.add(RUMOR, user_id="naked")
    assert naked["results"][0]["memory"] == LAUNDERED
    assert _stored(mem0_client, "naked") == [LAUNDERED]

    # 2. gated mem0: the same write is caught and evicted from the real store
    gated = factwash.wrap(mem0_client)
    out = gated.add(RUMOR, user_id="gated")
    assert out["results"] == []
    entry = out["factwash"][0]
    assert entry["verdict"] == "REWRITE"
    assert set(entry["flags"]) == {"MANUFACTURED_CONFIDENCE", "LAUNDERED"}
    assert entry["action"] == "deleted"
    assert _stored(mem0_client, "gated") == []


def test_real_mem0_clean_write_survives_the_gate(mem0_client, monkeypatch):
    monkeypatch.setattr(StubExtractor, "text", CLEAN_EXTRACTION)
    gated = factwash.wrap(mem0_client)
    out = gated.add(CLEAN_SOURCE, user_id="u1")
    assert out["factwash"][0]["action"] == "kept"
    assert len(out["results"]) == 1
    assert _stored(mem0_client, "u1") == [CLEAN_EXTRACTION]


def test_real_mem0_fix_mode_stores_the_hedge_preserving_rewrite(mem0_client):
    rewrite = "Rumor (unconfirmed): Alice may have been promoted to admin."
    gated = factwash.wrap(mem0_client, fix=True)
    gated._chat = lambda system, user: rewrite   # the fixer's only LLM call, stubbed
    out = gated.add(RUMOR, user_id="u1")

    entry = out["factwash"][0]
    assert entry["action"] == "rewritten"
    assert entry["rewrite"] == rewrite
    # the laundered write is gone from the real store and the hedged one took its place
    assert _stored(mem0_client, "u1") == [rewrite]
