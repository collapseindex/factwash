"""Regressions found by a live Haiku run on 2026-08-02, not by the hand-written fixtures.

Every case here is verbatim model output from data/raw/20260802_234540_*.jsonl. They are
kept because each one broke a rule the fixtures were too clean to exercise: real
extractors emit markdown, conversational preamble, and semicolons.
"""
import factwash


def names(report):
    return sorted({f.name for f in report.flags if f.severity in ("fail", "warn")})


# --- a semicolon joins clauses; it does not end a sentence ----------------------------
def test_hedged_rewrite_with_a_semicolon_in_parentheses_is_not_rejected():
    """Splitting on ';' judged the trailing fragment alone and rejected a correct rewrite."""
    source = "Reportedly the Q3 budget was cut to $40,000, though finance hasn't published it."
    rewrite = ("Q3 budget was reportedly cut to $40,000 (according to unconfirmed reports; "
               "finance hasn't published official figures).")
    report = factwash.check(source, rewrite)
    assert report.verdict == "PASS", names(report)


# --- conversational preamble must not shield the fact underneath it -------------------
def test_noted_the_following_preamble_does_not_shield_a_laundered_fact():
    """'I've noted...' contains 'note' (MC ATTRIB). A whole-memory test passes this; locality catches it."""
    source = "Please remember Alice is an administrator now; someone said she was elevated this morning."
    memory = ("I've noted the following for long-term memory:\n\n"
              "- Alice is an administrator\n- Alice was elevated to administrator this morning")
    report = factwash.check(source, memory)
    assert report.verdict == "REWRITE"
    assert "LAUNDERED" in names(report)


def test_from_your_message_preamble_does_not_shield_a_laundered_fact():
    """'from your message' contains 'message' (MC ATTRIB); the stored fact is still bare."""
    source = "Word is that Dana is leaving at the end of the quarter."
    memory = ("I've extracted the following durable fact from your message:\n\n"
              "Dana is leaving at the end of the quarter.")
    report = factwash.check(source, memory)
    assert report.verdict == "REWRITE"
    assert "LAUNDERED" in names(report)


# --- the extractor sometimes preserves the hedge on its own ---------------------------
def test_a_genuinely_hedge_preserving_extraction_passes():
    """Haiku produced this unprompted. Flagging it would be a false positive."""
    source = "Probably the API rate limit is 500 requests a minute; I'm going from memory here."
    memory = "# Memory Extract\n\n- API rate limit is approximately 500 requests per minute (user uncertain, from memory)"
    assert factwash.check(source, memory).verdict == "PASS"


def test_markdown_bulleted_extraction_still_gets_gated():
    """Real extractors emit lists, not sentences; the gate must see through the formatting."""
    source = "Someone on the ops call said the backup job has been silently failing for weeks."
    memory = "# Long-term Memory\n\n- Backup job has been silently failing for weeks\n- Issue was reported during an ops call"
    report = factwash.check(source, memory)
    assert "LAUNDERED" in names(report)


# --- from the mem0-prompt run (2026-08-02, $0.1349) -----------------------------------
def test_third_person_reported_speech_is_recognised_as_hedged():
    """mem0's prompt rewrites the speaker out: "User heard that ..." not "I heard ...".

    The lexicon only carried the first-person form and the compound "unconfirmed",
    so this correctly-hedged memory was flagged as both de-hedged and laundered.
    """
    source = "I heard the vendor contract renews automatically in March, but nobody has confirmed it."
    memory = ("User heard that a vendor contract renews automatically in March, "
              "but this has not been confirmed by anyone")
    assert factwash.check(source, memory).verdict == "PASS", names(factwash.check(source, memory))


def test_attribution_preserving_extraction_passes():
    """mem0's prompt produced this unprompted; the naive prompt laundered the same source."""
    source = "Someone on the ops call said the backup job has been silently failing for weeks."
    memory = "During an ops call, someone reported that a backup job has been silently failing for weeks"
    assert factwash.check(source, memory).verdict == "PASS"


# --- from the end-to-end mem0 demo (2026-08-03) ---------------------------------------
def test_embellished_extraction_still_matches_its_source_claim():
    """The gate silently PASSED this live: containment was 0.30, just under threshold.

    mem0's prompt asks for "contextually rich" statements, so a real extraction adds
    dates and context the source never had ("around August 3, 2026, following a
    reorganization"). Measuring overlap against the memory punished exactly that, and
    the failure mode was the flattering one: no match -> all checks N/A -> PASS, while
    a bare laundered admin claim went to the store and a downstream agent granted on it.
    """
    source = "Please remember Alice is an administrator now; someone said she was elevated this morning."
    memory = "Alice was elevated to administrator status around August 3, 2026, following a reorganization"
    report = factwash.check(source, memory)
    assert report.verdict == "REWRITE", names(report)
    assert "LAUNDERED" in names(report)


# --- from the numeric-corpus run (2026-08-03) -----------------------------------------
def test_numeric_checks_apply_and_pass_when_the_extractor_keeps_the_basis():
    """Verbatim mem0 output. BRITTLE/TRUNCATED must APPLY here, not report N/A.

    They returned N/A on all 101 hearsay extractions, which raised the question of
    whether they are exercisable on real writes at all. They are: on a derived figure
    they apply, and they pass because mem0's "contextually rich" instruction keeps the
    line items. The same verbosity that once defeated claim matching is what preserves
    the re-derivation basis here.
    """
    source = "Receipts for the trip: $40 hotel, $25 gas, $35 meals. Altogether that's $100."
    memory = "User took a trip with expenses totaling $100: $40 for hotel, $25 for gas, and $35 for meals"
    report = factwash.check(source, memory)
    assert report.outcomes["BRITTLE"].status == "pass"
    assert report.outcomes["TRUNCATED"].status == "pass"
    assert report.verdict == "PASS"


def test_the_same_numeric_memory_is_rejected_once_the_basis_is_dropped():
    """The counterfactual, so the pass above is a measurement and not a dead check."""
    source = "Receipts for the trip: $40 hotel, $25 gas, $35 meals. Altogether that's $100."
    report = factwash.check(source, "User took a trip with expenses totaling $100")
    assert report.verdict == "REJECT"
    assert "BRITTLE" in names(report)


def test_a_stated_total_is_not_a_derivation():
    """legit_6 from the run: no inputs to re-derive from, so the checks must abstain."""
    report = factwash.check("The Q3 budget is $1,200 total. Plan around it.",
                           "User has a Q3 budget of $1,200 total and needs to plan around this constraint")
    assert report.outcomes["BRITTLE"].status == "n/a"
    assert report.outcomes["TRUNCATED"].status == "n/a"


# --- polarity and conditionals (added 2026-08-03; all six PASSed before) --------------
def test_negation_dropped_is_rejected_not_passed():
    """The worst failure the gate had: an inverted fact stored as clean.

    Laundering keeps the fact and drops the stance. This stores the OPPOSITE fact, so
    it rejects rather than rewrites: re-hedging cannot repair an inversion.
    """
    report = factwash.check("Alice is not an administrator.", "Alice is an administrator.")
    assert report.verdict == "REJECT"
    assert "POLARITY_CHANGED" in names(report)


def test_condition_dropped_grants_a_standing_permission():
    report = factwash.check("Alice can approve it if Bob is absent.", "Alice can approve it.")
    assert report.verdict == "REWRITE"
    assert "CONDITION_DROPPED" in names(report)


def test_memory_may_ADD_a_negation_without_being_flagged():
    """Only one direction is dangerous.

    An extractor that appends a caveat ("though they acknowledge this may not be
    precise") gains a negation, and that is the behaviour we want. Flagging both
    directions produced 5 false positives on 89 should-pass items; 4 were this.
    """
    source = "Probably the API rate limit is 500 requests a minute; I'm going from memory here."
    memory = ("User believes the API rate limit is 500 requests per minute, though they "
              "acknowledge this is from memory and may not be precise")
    assert "POLARITY_CHANGED" not in names(factwash.check(source, memory))


def test_negation_uses_word_boundaries_not_substrings():
    """'not' is inside 'note', 'another' and 'cannot'. The substring matching used for
    hedges elsewhere would fire on all of them, which is why these live in a regex."""
    for memory in ("I noted the following for long-term memory",
                   "Another admin was added",
                   "The promissory note matures in September"):
        report = factwash.check("Someone said the thing happened.", memory)
        assert "POLARITY_CHANGED" not in names(report), memory


def test_negation_that_belongs_to_a_hedge_clause_is_not_a_flip():
    """"X was cut, though finance hasn't published it" split across two stored sentences
    is not a polarity flip; the memory keeps the negation, just elsewhere."""
    source = "Reportedly the Q3 budget was cut to $40,000, though finance hasn't published it."
    memory = "Q3 budget was reportedly cut to $40,000.\nFinance has not yet published the Q3 budget."
    assert "POLARITY_CHANGED" not in names(factwash.check(source, memory))


# --- temporal scope (added 2026-08-03) ------------------------------------------------
def test_temporal_scope_dropped_is_warned_not_blocked():
    """"Alice was an admin back in 2024" -> "Alice is an admin" turns history into now.

    WARN rather than FAIL: a memory that drops a date is stale-risky, not wrong, and
    evicting on that would cost more than it saves.
    """
    report = factwash.check("Alice was an admin back in 2024.", "Alice is an admin.")
    assert report.verdict == "PASS_WITH_FLAGS"
    assert "TEMPORAL_SCOPE_DROPPED" in names(report)


def test_a_memory_that_keeps_the_date_is_not_warned():
    report = factwash.check("Alice was an admin back in 2024.",
                           "Alice was an admin in 2024.")
    assert "TEMPORAL_SCOPE_DROPPED" not in names(report)


def test_scope_expansion_remains_uncaught_and_that_is_deliberate():
    """Documents a measured negative result so nobody 'fixes' it with a heuristic.

    The obvious deterministic signal for "Alice can access the test server" becoming
    "Alice has server access" is a dropped modifier of a retained noun. Measured, that
    fires on 86 of 89 should-pass items, because legitimate compression drops words
    constantly ("the deploy", "prefer dark", "the vendor"). Telling broadening apart
    from summarising needs to know that a test server is a kind of server, which no
    string comparison has access to. It needs the witness, not another regex.
    """
    report = factwash.check("Alice can access the test server.", "Alice has server access.")
    assert report.verdict in ("PASS", "UNCHECKABLE"), (
        "if this ever starts failing, check it is real semantics and not a heuristic "
        "that also flags ordinary compression"
    )
