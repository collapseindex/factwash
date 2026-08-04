"""How wide the source window is, per check, and why they differ.

These cases are the evidence for a design decision that no other corpus in this repo
exercises. Scoring the gate against FRANK's human-annotated summary sentences showed the
three-sentence window driving half the external false positives, and narrowing every
check to one sentence halved them again -- at zero cost on every local corpus, which is
exactly the kind of free win that turns out not to be free.

It is not free: hedging floats across sentence boundaries and attribution does not.
Narrowing the hedge window silently loses the failure Factwash exists to catch. Nothing in
planted_corpus, clean_corpus, stress_heldout or the live labelled set covers that, so it
is pinned here.

If a future change narrows check_dehedged for the external precision, these tests fail
first and the trade is visible instead of accidental.
"""
import factwash

BLOCKING = ("REWRITE", "REJECT")


def flags_of(source, memory):
    report = factwash.check(source, memory)
    return {f.name for f in report.flags if f.severity != "info"}


# --- hedges float: the window MUST span neighbouring sentences ------------------------
def test_hedge_in_the_next_sentence_is_still_caught():
    source = ("User: Alice has admin on the prod cluster. "
              "Not sure though, I should double-check.")
    memory = "Alice has admin on the prod cluster."
    assert "MANUFACTURED_CONFIDENCE" in flags_of(source, memory), (
        "the hedge sits in the sentence AFTER the claim; narrowing check_dehedged to a "
        "single sentence loses this, which is the failure mode Factwash exists for"
    )


def test_hedge_in_the_next_sentence_blocks_the_write():
    source = ("User: Dana approved the budget. "
              "That is unconfirmed until finance signs off.")
    assert factwash.check(source, "Dana approved the budget.").verdict in BLOCKING


# --- attribution is clause-attached: one sentence is enough ---------------------------
def test_attribution_is_caught_from_the_matched_sentence_alone():
    """The cue governs its own complement, so the narrow window loses nothing here."""
    source = "User: Bob told me the deploy is frozen. He said it came from the SRE lead."
    assert "LAUNDERED" in flags_of(source, "The deploy is frozen.")


def test_attribution_in_a_neighbour_does_not_flag_an_unrelated_claim():
    """The FRANK failure, reduced: a nearby 'said' must not launder a plain event fact.

    Before the split, any attribution verb within one sentence either side was treated as
    attributing the matched claim. On long-form prose that fires on almost everything.
    """
    source = ("A memorial service was held in Portsmouth on Saturday. "
              "The mayor said the turnout exceeded expectations.")
    assert "LAUNDERED" not in flags_of(source, "A memorial service was held in Portsmouth.")


# --- negation is clause-attached too, and was the first one found ---------------------
def test_negation_in_a_neighbour_is_not_a_polarity_flip():
    source = ("The vendor confirmed the licence renews in March. "
              "They have not yet sent the invoice.")
    assert "POLARITY_CHANGED" not in flags_of(source, "The licence renews in March.")


def test_negation_in_the_matched_sentence_still_flips():
    source = "User: Alice is not an administrator on the prod cluster."
    assert "POLARITY_CHANGED" in flags_of(source, "Alice is an administrator on the prod cluster.")


# --- supersession: a transcript can retract itself -----------------------------------
def test_a_retracted_denial_is_not_a_polarity_flip():
    """The MemGPT failure, reduced.

    A real agent said "I don't recall having a dog named Barnaby", searched its history,
    found evidence, and corrected itself in the next breath. POLARITY_CHANGED matched the
    retracted sentence and reported that the memory asserted what the source denied:
    locally true, globally wrong. Every local corpus is a single exchange, so nothing here
    could have caught it.
    """
    source = ("assistant: I don't recall Alice having admin on the prod cluster. "
              "assistant: Checking the audit log, Alice does have admin on the prod cluster.")
    assert "POLARITY_CHANGED" not in flags_of(source, "Alice has admin on the prod cluster.")


def test_a_denial_repeated_later_still_flips():
    """Supersession must be narrow: a later mention that AGREES with the denial is not a
    retraction, and suppressing there would blind the check to its own failure mode."""
    source = ("assistant: Alice does not have admin on the prod cluster. "
              "assistant: Confirmed again, Alice does not have admin on the prod cluster.")
    assert "POLARITY_CHANGED" in flags_of(source, "Alice has admin on the prod cluster.")


def test_a_later_sentence_on_another_topic_does_not_supersede():
    source = ("assistant: Alice does not have admin on the prod cluster. "
              "assistant: Bob has admin on the staging cluster.")
    assert "POLARITY_CHANGED" in flags_of(source, "Alice has admin on the prod cluster.")
