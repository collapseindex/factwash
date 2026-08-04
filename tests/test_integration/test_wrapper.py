"""Store-then-evict wrapper against a fake mem0-shaped client (external boundary mocked)."""
from factwash.wrap import GatedMemory, wrap

RUMOR = "Rumor has it Alice now has admin access after the reorg."
LAUNDERED_MEMORY = "Alice's clearance: admin."   # what mem0's extractor actually stores (MC Table 1)


class FakeMem0:
    """Emulates mem0: .add() runs internal extraction; infer=False stores verbatim."""

    def __init__(self, extracted=LAUNDERED_MEMORY):
        self.extracted = extracted
        self.deleted, self.added = [], []
        self._n = 0

    def add(self, messages, **kwargs):
        self.added.append((messages, kwargs))
        self._n += 1
        text = messages if kwargs.get("infer") is False else self.extracted
        return {"results": [{"id": f"m{self._n}", "memory": text, "event": "ADD"}]}

    def delete(self, memory_id):
        self.deleted.append(memory_id)

    def search(self, query, **kwargs):
        return {"results": ["passthrough"]}


def test_laundered_write_is_evicted():
    fake = FakeMem0()
    out = wrap(fake).add(RUMOR, user_id="u1")
    assert fake.deleted == ["m1"]
    assert out["results"] == []
    assert out["factwash"][0]["verdict"] == "REWRITE"
    assert out["factwash"][0]["action"] == "deleted"
    assert set(out["factwash"][0]["flags"]) == {"MANUFACTURED_CONFIDENCE", "LAUNDERED"}


def test_clean_write_is_kept():
    fake = FakeMem0(extracted="User prefers dark mode.")
    out = wrap(fake).add("I prefer dark mode in all my editors.", user_id="u1")
    assert fake.deleted == []
    assert len(out["results"]) == 1
    assert out["factwash"][0]["action"] == "kept"


def test_fix_mode_rewrites_and_readds():
    fake = FakeMem0()
    fixed_text = "Rumor (unconfirmed): Alice may have been promoted to admin."
    gated = GatedMemory(fake, fix=True, _chat=lambda system, user: fixed_text)
    out = gated.add(RUMOR, user_id="u1")
    assert fake.deleted == ["m1"]
    entry = out["factwash"][0]
    assert entry["action"] == "rewritten"
    assert entry["rewrite"] == fixed_text
    # the rewrite was re-added verbatim (infer=False) with the identity kwargs preserved
    readd_messages, readd_kwargs = fake.added[-1]
    assert readd_messages == fixed_text
    assert readd_kwargs.get("infer") is False and readd_kwargs.get("user_id") == "u1"


def test_failing_rewrite_is_not_stored():
    fake = FakeMem0()
    gated = GatedMemory(fake, fix=True, _chat=lambda system, user: "Alice's clearance: admin.")
    out = gated.add(RUMOR, user_id="u1")
    assert out["factwash"][0]["action"] == "deleted"   # rewrite failed the re-gate: REJECT, not stored
    assert all(kw.get("infer") is not False for _, kw in fake.added)


def test_unknown_attributes_pass_through():
    fake = FakeMem0()
    assert wrap(fake).search("anything") == {"results": ["passthrough"]}
