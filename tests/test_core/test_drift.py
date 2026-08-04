"""Multi-hop drift: hop attribution, the composition property, and loud checkability
loss. The chains here are the probe chains the module's claims were measured on."""
import pytest

from factwash.drift import drift

CLASSIC = [
    "Someone said Alice may have admin access until Friday.",
    "Reportedly, Alice may have admin access until Friday.",
    "Alice reportedly has admin access until Friday.",
    "Alice reportedly has admin access.",
    "Alice has admin access.",
]

PARAPHRASE = [
    "Someone mentioned the Berlin office might close after the merger review.",
    "The Berlin site could shut down following the merger assessment.",
    "Post-merger evaluation may end operations in Berlin.",
    "German location closure is expected.",
]


# --- hop attribution ------------------------------------------------------------------
def test_end_to_end_changes_are_attributed_to_their_hops():
    r = drift(CLASSIC)
    assert r.hop_of[("DROPPED", "temporal scope")] == 3
    assert r.hop_of[("DROPPED", "attribution")] == 4


def test_class_straddling_cue_delays_the_loss_to_the_hop_that_drops_it():
    """'reportedly' reads as hedge and attribution at once, so hops 1-3 look clean on
    certainty and the strengthening surfaces only when the straddling cue drops at
    hop 4, together with the attribution loss. Measured, not designed."""
    r = drift(CLASSIC)
    assert r.hop_of[("STRENGTHENED", "certainty")] == 4
    assert not any((c.type, c.property) == ("STRENGTHENED", "certainty")
                   for h in r.hops[:3] for c in h.changes)


def test_unattributed_change_renders_as_end_to_end_only():
    """No natural chain in the fixtures produces a change no hop shows, so the fallback
    is unit-tested directly: it must render, else the None path is decoration."""
    import factwash
    from factwash.drift import DriftReport
    end = factwash.inspect("According to Jason, Alice may have access until Friday.",
                           "Alice has access.")
    clean_hop = factwash.inspect("I think the deploy might be risky.",
                                 "User thinks the deploy might be risky.")
    r = DriftReport(versions=2, hops=[clean_hop], end_to_end=end,
                    hop_of={(c.type, c.property): None for c in end.changes})
    assert "only visible end-to-end" in r.render()


# --- the composition property ---------------------------------------------------------
def test_in_lexicon_chain_cannot_launder_gradually():
    """The first hop that drops a class's last cue fires, so the ends laundering
    implies some hop was gate-blocked. Pinned on the probe chain."""
    r = drift(CLASSIC)
    assert r.end_to_end.gate.verdict in ("REWRITE", "REJECT")
    assert any(h.gate.verdict in ("REWRITE", "REJECT") for h in r.hops)
    assert r.gradual is False


def test_gradual_flag_logic_both_ways():
    """No in-lexicon gradual chain is known, so the flag's logic is unit-tested
    directly: it must be able to go True, else it is decoration."""
    r = drift(CLASSIC)
    assert r.gradual is False
    # end launders, hops all pass -> gradual
    class _G:                                    # minimal stand-ins with .gate.verdict
        def __init__(self, verdict): self.gate = type("g", (), {"verdict": verdict})()
    from factwash.drift import DriftReport
    fake = DriftReport(versions=3, hops=[_G("PASS"), _G("PASS_WITH_FLAGS")],
                       end_to_end=_G("REWRITE"))
    assert fake.gradual is True


# --- checkability loss ----------------------------------------------------------------
def test_paraphrase_chain_loses_checkability_loudly():
    r = drift(PARAPHRASE)
    assert r.checkability_lost_at == 2
    assert "CHECKABILITY LOST at hop 2" in r.render()


def test_clean_chain_reports_no_loss_and_no_changes():
    r = drift(["I think the deploy might be risky.",
               "User thinks the deploy might be risky."])
    assert r.checkability_lost_at is None
    assert r.end_to_end.verdict == "PRESERVED"
    assert r.gradual is False


# --- contract -------------------------------------------------------------------------
def test_single_version_raises():
    with pytest.raises(ValueError):
        drift(["only one"])


def test_to_dict_round_trips():
    d = drift(CLASSIC).to_dict()
    assert d["versions"] == 5 and len(d["hops"]) == 4
    assert d["gradual_laundering"] is False
    assert d["checkability_lost_at_hop"] is None
    assert {(a["type"], a["property"]) for a in d["change_attribution"]} == {
        ("STRENGTHENED", "certainty"), ("DROPPED", "attribution"),
        ("DROPPED", "temporal scope")}
