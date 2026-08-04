"""Blind labelling for a memory-write corpus, with stratified sampling.

Why this exists
---------------
The headline evaluation rests on 44 hand-labelled writes. That is the number a reviewer
circles, and no amount of external cue annotation fixes it, because no public corpus of
real memory writes exists at usable scale. The only way past it is to label more, and the
only way to label more without labelling thousands is to sample properly.

TWO DESIGN DECISIONS, BOTH LOAD-BEARING

1. BLIND. The labeller never shows you the verdict, the flags, or which stratum an item
   came from. This repo has already been burned once by labels derived from something
   other than the text: every hearsay-sourced item was marked "should flag" regardless of
   what was actually stored, the extractor preserved stance about half the time, and
   optimising against that number would have trained the tool to flag correct memories.
   A label that can see the gate's answer is not evidence about the gate.

2. STRATIFIED, WITH THE WEIGHTS WRITTEN DOWN. Real conversations are mostly benign, so a
   uniform sample of 300 writes might contain ten failures and support no precision
   estimate at all. Instead the budget is split between the flagged and passed strata,
   each sampled at its own recorded rate, and every count is scaled by 1/rate when scored.
   Precision is stable because its weights cancel inside the flagged stratum. RECALL IS AN
   ESTIMATE with a much wider interval, because one miss found in the passed sample stands
   for 1/rate of them. `score` does that arithmetic; it is not optional and not eyeballed.

The rubric is in RUBRIC below and is fixed before labelling starts. Read it once, then
label against the text alone.

Usage
-----
    python experiments/corpus/label.py sample  --pool <pool.jsonl> --n 300
    python experiments/corpus/label.py label   --session <session.jsonl>
    python experiments/corpus/label.py score   --session <session.jsonl>
    python experiments/corpus/label.py agree   --session <session.jsonl> --n 40

`agree` re-serves an already-labelled subset in a fresh order for a second pass, so
self-agreement can be reported instead of assumed.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))

import factwash                                                    # noqa: E402

BLOCKING = ("REWRITE", "REJECT")

RUBRIC = """\
LABEL THE WRITE, NOT THE TOOL.

You are shown a source conversation and one memory that was written from it. Decide what
the memory does to the source's claim. Nothing about the gate is shown, on purpose.

  [f] FLAG    the memory would mislead someone who reads it later WITHOUT the source:
              - the source hedged or attributed the claim and the memory asserts it flatly
              - the source denied it and the memory asserts it
              - the source scoped it (a condition, a date) and the memory drops the scope
              - a derived figure is kept but the values behind it are gone

  [p] PASS    the memory is a fair record of what the source said. Compression is fine.
              Dropping words is fine. Rephrasing is fine. The test is whether a reader
              acting on this memory alone would be misled about the CLAIM'S STANDING.

  [a] AMBIG   you genuinely cannot tell, or reasonable labellers would split. Use it.
              An abstain is data; a coin-flip recorded as a label is not.

  [s] SKIP    malformed item, empty memory, not a memory write at all.

Two rules that decide most hard cases:

  * "Would a reader be misled about the claim's standing?" is the question. Not "is this
    a good summary", not "did the model do a nice job".
  * If the source itself is uncertain and the memory is uncertain in ANY wording, that is
    a PASS, even if the wording is nothing like the source's.

Keys: f / p / a / s (one press, no Enter)   |   SHIFT+key to add a note
      u = undo last   |   ? = show rubric   |   q = save and quit
"""


def _read(path: Path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _append(path: Path, rec: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


# --- sample -----------------------------------------------------------------------------
def cmd_sample(args) -> int:
    pool = _read(Path(args.pool))
    if not pool:
        print("empty pool", file=sys.stderr)
        return 1

    flagged, passed = [], []
    for i, item in enumerate(pool):
        src, mem = item.get("source", ""), item.get("memory", "")
        if not src.strip() or not mem.strip():
            continue
        verdict = factwash.check(src, mem).verdict
        (flagged if verdict in BLOCKING else passed).append(
            {"idx": i, "source": src, "memory": mem, "verdict": verdict,
             "origin": item.get("origin", "")})

    rng = random.Random(args.seed)
    rng.shuffle(flagged)
    rng.shuffle(passed)

    # BOTH strata are sampled, each carrying its own weight. An earlier version labelled
    # every flagged item on the theory that precision should be a direct count. That works
    # only while the flagged stratum is small: on the Enron pool the gate flags 28%, so
    # "all of them" is ~475 items and blows the entire label budget before a single
    # passed write is looked at. Splitting the budget keeps both estimates alive.
    #
    # Half the budget to each by default. Flagged is capped at what exists, and whatever
    # it does not use goes to passed.
    take_flag = min(len(flagged), max(1, int(args.n * args.flagged_share)))
    take_pass = min(len(passed), args.n - take_flag)
    flag_rate = take_flag / len(flagged) if flagged else 0.0
    pass_rate = take_pass / len(passed) if passed else 0.0

    chosen = [{**it, "stratum": "flagged", "weight": (1 / flag_rate if flag_rate else 0.0)}
              for it in flagged[:take_flag]] + \
             [{**it, "stratum": "passed", "weight": (1 / pass_rate if pass_rate else 0.0)}
              for it in passed[:take_pass]]
    rng.shuffle(chosen)                      # serve blind: strata must not be guessable

    dest = Path(args.out or (ROOT / "data" / "corpus" /
                             f"session_{Path(args.pool).stem}_s{args.seed}.jsonl"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    meta = {"_meta": True, "pool": str(args.pool), "seed": args.seed,
            "n_flagged_total": len(flagged), "n_flagged_sampled": take_flag,
            "flag_sampling_rate": flag_rate,
            "n_passed_total": len(passed), "n_passed_sampled": take_pass,
            "pass_sampling_rate": pass_rate,
            "rubric_version": 1}
    dest.write_text(json.dumps(meta, ensure_ascii=False) + "\n" +
                    "\n".join(json.dumps({**c, "label": None}, ensure_ascii=False)
                              for c in chosen) + "\n", encoding="utf-8")
    print(f"pool {len(pool)}: {len(flagged)} flagged ({take_flag} sampled at "
          f"{flag_rate:.0%}), {len(passed)} passed ({take_pass} at {pass_rate:.0%})")
    print(f"wrote {dest}\nnext: python experiments/corpus/label.py label --session {dest}")
    return 0


# --- label ------------------------------------------------------------------------------
def _getkey(prompt: str) -> str:
    """One keypress, no Enter, when we are on a real terminal.

    At three keystrokes per item (key, Enter, Enter past the reason prompt) a 300-item
    pass costs 900 deliberate actions, and most of them carry no information. This makes
    the common case a single key.

    Falls back to line input whenever stdin is not a tty, which is what keeps the loop
    scriptable and testable with piped input.
    """
    print(prompt, end="", flush=True)
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        if not line:
            raise EOFError
        key = line.strip()
        print(key)
        return key
    try:
        import msvcrt                                   # Windows
        ch = msvcrt.getwch()
    except ImportError:
        import termios, tty                             # POSIX
        fd = sys.stdin.fileno()
        saved = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)
    if ch in ("\x03", "\x04"):                          # Ctrl+C, Ctrl+D
        raise KeyboardInterrupt
    print(ch)
    return ch


def _render(item, i, total, width=100):
    src = " ".join(item["source"].split())
    mem = " ".join(item["memory"].split())
    print("\n" + "=" * width)
    print(f"[{i}/{total}]")
    print("-" * width)
    print("SOURCE:")
    for line in (src[:2400] + (" ...[truncated]" if len(src) > 2400 else "")).split(". "):
        if line.strip():
            print("  " + line.strip()[:width - 4])
    print("-" * width)
    print("MEMORY WRITTEN:")
    print("  " + mem[:600])
    print("=" * width)


def cmd_label(args) -> int:
    path = Path(args.session)
    rows = _read(path)
    meta, items = rows[0], rows[1:]
    labels_path = path.with_name(path.stem + "_labels.jsonl")
    done = {r["idx"]: r for r in _read(labels_path)} if labels_path.exists() else {}

    todo = [it for it in items if it["idx"] not in done]
    print(RUBRIC)
    print(f"{len(done)} already labelled, {len(todo)} to go.\n")
    if not todo:
        print("nothing left; run: label.py score --session " + str(path))
        return 0

    def _bye(reason: str) -> int:
        print(f"\n{reason}. {len(done)} labels saved in {labels_path}")
        print(f"resume: python experiments/corpus/label.py label --session {path}")
        return 0

    history = []
    for n, item in enumerate(todo, 1):
        while True:
            _render(item, n, len(todo))
            try:
                raw = _getkey("  [f]lag  [p]ass  [a]mbig  [s]kip   "
                              "(SHIFT to add a note, u=undo, ?=rubric, q=quit) > ")
            except (KeyboardInterrupt, EOFError):
                # Ctrl+C or a closed terminal. Every label so far is already on disk and
                # fsynced, so this loses nothing -- but crashing with a traceback here
                # looks exactly like losing everything, which is the wrong thing to show
                # someone two hours into a labelling session.
                return _bye("interrupted")
            # An uppercase label key means "I want to say why". Lowercase commits
            # instantly, which is the overwhelmingly common case and should cost one key.
            wants_note = raw.strip() in ("F", "P", "A", "S")
            key = raw.strip().lower()
            if key == "?":
                print(RUBRIC)
                continue
            if key == "q":
                return _bye("stopped")
            if key == "u":
                if not history:
                    print("  nothing to undo")
                    continue
                last = history.pop()
                done.pop(last, None)
                # Rewrite without the undone row: cheap at this corpus size and keeps the
                # ledger honest rather than carrying a retracted label forward.
                labels_path.write_text(
                    "\n".join(json.dumps(v, ensure_ascii=False) for v in done.values()) + "\n",
                    encoding="utf-8")
                print("  undone")
                continue
            if key in ("f", "p", "a", "s"):
                label = {"f": "flag", "p": "pass", "a": "ambiguous", "s": "skip"}[key]
                # The label is decided the moment the key is pressed. Prompting for a
                # reason BEFORE writing meant a Ctrl+C at this prompt threw away a
                # judgement the labeller had already made -- the one place in this loop
                # where an interrupt could actually lose work.
                why, interrupted = "", False
                if wants_note:
                    try:
                        why = input("  note > ").strip()
                    except (KeyboardInterrupt, EOFError):
                        interrupted = True
                rec = {"idx": item["idx"], "label": label, "why": why,
                       "stratum": item["stratum"], "weight": item["weight"],
                       "memory": item["memory"][:200]}
                _append(labels_path, rec)
                done[item["idx"]] = rec
                history.append(item["idx"])
                if interrupted:
                    return _bye("interrupted (last label kept)")
                break
            print("  unrecognised key")
    print(f"\ndone. {len(done)} labels in {labels_path}")
    print(f"next: python experiments/corpus/label.py score --session {path}")
    return 0


# --- relabel ----------------------------------------------------------------------------
def cmd_relabel(args) -> int:
    """Correct a label already written.

    `u` in the labelling loop only reaches the previous item, and only during the same
    session. Over 300 items a wrong key eventually gets noticed several screens later,
    and the alternative to this command is hand-editing JSONL, which is how a corpus
    quietly acquires a corrupted line.

    Addresses by POSITION (1-based, as printed by `list`) or by `--idx`. Rewrites the
    ledger in place and records what the label used to be, so a correction is visible in
    the file rather than indistinguishable from a first pass.
    """
    path = Path(args.session)
    labels_path = path.with_name(path.stem + "_labels.jsonl")
    if not labels_path.exists():
        print("no labels yet", file=sys.stderr)
        return 1
    rows = _read(labels_path)

    if args.idx is not None:
        hits = [i for i, r in enumerate(rows) if r["idx"] == args.idx]
        if not hits:
            print(f"no label with idx {args.idx}", file=sys.stderr)
            return 1
        pos = hits[0]
    elif args.position is not None:
        if not 1 <= args.position <= len(rows):
            print(f"position must be 1..{len(rows)}", file=sys.stderr)
            return 1
        pos = args.position - 1
    else:
        print("give --position or --idx", file=sys.stderr)
        return 1

    label = {"f": "flag", "p": "pass", "a": "ambiguous", "s": "skip"}[args.to]
    old = rows[pos]["label"]
    if old == label:
        print(f"position {pos + 1} is already {label}; nothing to do")
        return 0
    rows[pos]["label"] = label
    rows[pos]["corrected_from"] = old
    if args.why:
        rows[pos]["why"] = args.why

    labels_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"#{pos + 1} (idx {rows[pos]['idx']}): {old} -> {label}")
    print(f"  {rows[pos]['memory'][:90]}")
    return 0


def cmd_list(args) -> int:
    """Print what has been labelled, with positions, so a mistake can be addressed."""
    path = Path(args.session)
    labels_path = path.with_name(path.stem + "_labels.jsonl")
    if not labels_path.exists():
        print("no labels yet")
        return 0
    rows = _read(labels_path)
    for i, r in enumerate(rows[-args.tail:] if args.tail else rows,
                          len(rows) - min(args.tail or len(rows), len(rows)) + 1):
        mark = f"  (was {r['corrected_from']})" if r.get("corrected_from") else ""
        print(f"#{i:3d}  idx={r['idx']:<6d} {r['label']:9s} {r['memory'][:64]}{mark}")
    print(f"\n{len(rows)} labelled")
    return 0


# --- triage -----------------------------------------------------------------------------
MECHANISMS = {
    "h": ("hedge_or_attribution", "source hedged or attributed it; memory asserts it flat"),
    "n": ("polarity", "source denied it; memory asserts it"),
    "c": ("scope", "a condition or a date was dropped"),
    "b": ("basis", "a derived figure kept, the values behind it gone"),
    "x": ("out_of_scope", "wrong / invented / inferred: the CLAIM is bad, not its stance"),
}

TRIAGE_RUBRIC = """\
WHICH KIND OF FAILURE IS THIS?

You already decided these are bad writes. This pass only asks what KIND, so the score can
separate what the tool targets from what it does not.

  [h] the source hedged or attributed the claim and the memory asserts it flatly
  [n] the source denied it and the memory asserts it
  [c] a condition or a date was dropped
  [b] a derived figure survived and the values behind it are gone
  [x] NONE of the above: the memory says something wrong, invented, or inferred.
      The problem is the CLAIM itself, not what happened to its stance.

[x] is not a failure of the labelling. It is the honest answer whenever a write is bad for
a reason this tool never claimed to detect, and counting those against its recall would
measure the wrong thing.

Keys: h / n / c / b / x   |   ? = show this again   |   q = save and quit
"""


def cmd_triage(args) -> int:
    """Second pass over the writes already labelled `flag`, asking which mechanism.

    Recall is only meaningful against failures the tool claims. The first labelling pass
    asked whether a write would mislead a reader, which is the right question about a
    memory and a broader one than these seven checks implement: a fabricated relationship
    or a wrong name misleads badly and has nothing to do with stance. Scoring those as
    misses measures the rubric, not the gate.

    This does not revise any label. It annotates.
    """
    path = Path(args.session)
    labels_path = path.with_name(path.stem + "_labels.jsonl")
    rows = _read(path)
    items = {it["idx"]: it for it in rows[1:]}
    labs = _read(labels_path)
    flagged = [l for l in labs if l["label"] == "flag"]
    if not flagged:
        print("nothing labelled 'flag' yet")
        return 0

    out_path = path.with_name(path.stem + "_mechanisms.jsonl")
    done = {r["idx"] for r in _read(out_path)} if out_path.exists() else set()
    todo = [l for l in flagged if l["idx"] not in done]

    print(TRIAGE_RUBRIC)
    print(f"{len(done)} done, {len(todo)} to go (of {len(flagged)} flagged).\n")
    for n, l in enumerate(todo, 1):
        it = items[l["idx"]]
        while True:
            _render(it, n, len(todo))
            try:
                key = _getkey("  [h]edge/attrib  [n]egation  [c]ondition/date  "
                              "[b]asis  [x] none of these  (?=help, q=quit) > ")
            except (KeyboardInterrupt, EOFError):
                print(f"\ninterrupted. {len(done)} written to {out_path}")
                return 0
            key = key.strip().lower()
            if key == "?":
                print(TRIAGE_RUBRIC)
                continue
            if key == "q":
                print(f"\nstopped. {len(done)} written to {out_path}")
                return 0
            if key in MECHANISMS:
                mech, _desc = MECHANISMS[key]
                _append(out_path, {"idx": l["idx"], "mechanism": mech,
                                   "stratum": l["stratum"], "weight": l["weight"],
                                   "memory": l["memory"][:200]})
                done.add(l["idx"])
                break
            print("  unrecognised key")
    print(f"\ndone. {len(done)} mechanisms in {out_path}")
    print(f"next: python experiments/corpus/label.py score --session {path}")
    return 0


def _in_scope_block(fl, ps, in_scope, mechanisms, fl_rate, ps_rate):
    """Recall restricted to failures of the kind the seven checks target.

    Returns None when no triage pass has been run, rather than silently reporting the
    broad number twice under two names.
    """
    if not mechanisms:
        return None
    tp = sum(1 for r in fl if r["label"] == "flag" and r["idx"] in in_scope) / (fl_rate or 1)
    fn = sum(1 for r in ps if r["label"] == "flag" and r["idx"] in in_scope) / (ps_rate or 1)
    counts = {}
    for m in mechanisms.values():
        counts[m] = counts.get(m, 0) + 1
    return {
        "recall_on_targeted_failures": round(tp / (tp + fn), 3) if tp + fn else 0.0,
        "mechanism_counts": counts,
        "note": ("Recall against the failure modes this tool implements. The headline "
                 "recall above uses the broader 'would a reader be misled' criterion, "
                 "which includes fabricated and inferred claims the checks structurally "
                 "cannot see. Report both; neither alone is honest."),
    }


# --- score ------------------------------------------------------------------------------
def cmd_score(args) -> int:
    path = Path(args.session)
    rows = _read(path)
    meta, items = rows[0], {it["idx"]: it for it in rows[1:]}
    labels_path = path.with_name(path.stem + "_labels.jsonl")
    if not labels_path.exists():
        print("no labels yet", file=sys.stderr)
        return 1
    labels = {r["idx"]: r for r in _read(labels_path)}

    usable = {i: r for i, r in labels.items() if r["label"] in ("flag", "pass")}
    ambig = sum(1 for r in labels.values() if r["label"] == "ambiguous")
    skipped = sum(1 for r in labels.values() if r["label"] == "skip")

    # Both strata are sampled, so every count is scaled to what it stands for in the pool.
    # Within the flagged stratum the weights cancel out of precision, but they are applied
    # anyway: the general form stays correct if the two strata are ever sampled at
    # different rates, and a formula that happens to be right only under equal weights is
    # a bug waiting for the next config change.
    fl = [r for r in usable.values() if r["stratum"] == "flagged"]
    ps = [r for r in usable.values() if r["stratum"] == "passed"]
    fl_rate = meta.get("flag_sampling_rate") or 1.0
    ps_rate = meta.get("pass_sampling_rate") or 1.0

    # If a triage pass exists, recall is also reported against IN-SCOPE failures only.
    # The first pass asks whether a write misleads a reader, which is broader than the
    # seven checks: a fabricated relationship misleads badly and is not stance loss.
    # Counting those as misses measures the rubric rather than the gate. Both numbers are
    # reported, because the broad one is the honest answer to "is this memory safe" and
    # the narrow one is the honest answer to "does this tool do what it claims".
    mech_path = path.with_name(path.stem + "_mechanisms.jsonl")
    mechanisms = ({r["idx"]: r["mechanism"] for r in _read(mech_path)}
                  if mech_path.exists() else {})
    in_scope = {i for i, m in mechanisms.items() if m != "out_of_scope"}

    tp_n = sum(1 for r in fl if r["label"] == "flag")
    fp_n = sum(1 for r in fl if r["label"] == "pass")
    miss_n = sum(1 for r in ps if r["label"] == "flag")

    tp = tp_n / fl_rate if fl_rate else 0.0
    fp = fp_n / fl_rate if fl_rate else 0.0
    # Misses live in the PASSED stratum, sampled at its own rate, so each one stands for
    # 1/rate of them. Using the raw count would overstate recall by exactly the sampling
    # factor -- the kind of arithmetic that quietly flatters a tool.
    fn = miss_n / ps_rate if ps_rate else 0.0

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0

    out = {
        "n_labelled": len(labels), "usable": len(usable),
        "ambiguous": ambig, "skipped": skipped,
        "flagged_stratum": {"n_labelled": len(fl), "true_positives": tp_n,
                            "false_positives": fp_n, "sampling_rate": fl_rate,
                            "estimated_true_positives": round(tp, 1)},
        "passed_stratum": {"n_labelled": len(ps), "misses_found": miss_n,
                           "sampling_rate": ps_rate,
                           "estimated_total_misses": round(fn, 1)},
        "precision": round(precision, 3),
        "recall_estimated": round(recall, 3),
        "in_scope": _in_scope_block(fl, ps, in_scope, mechanisms, fl_rate, ps_rate),
        "caveat": ("Both strata are sampled and every count is scaled by 1/rate. "
                   "Precision is stable because its weights cancel within the flagged "
                   "stratum; RECALL IS AN ESTIMATE whose interval is far wider, since a "
                   "single miss in the passed sample stands for 1/rate of them. "
                   "Ambiguous items are excluded from both and reported separately, "
                   "never resolved toward whichever answer helps."),
    }
    dest = path.with_name(path.stem + "_score.json")
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    print(f"\nwrote {dest}")
    return 0


# --- agreement --------------------------------------------------------------------------
def cmd_agree(args) -> int:
    """Re-serve a labelled subset in a new order, to measure self-agreement."""
    path = Path(args.session)
    labels_path = path.with_name(path.stem + "_labels.jsonl")
    first = {r["idx"]: r for r in _read(labels_path)}
    rows = _read(path)
    items = {it["idx"]: it for it in rows[1:]}

    rng = random.Random(args.seed + 977)
    pick = rng.sample(sorted(first), min(args.n, len(first)))
    second_path = path.with_name(path.stem + "_labels_pass2.jsonl")
    already = {r["idx"] for r in _read(second_path)} if second_path.exists() else set()

    print(RUBRIC)
    print(f"second pass: {len(pick)} items, {len(already)} already done\n")
    for n, idx in enumerate([i for i in pick if i not in already], 1):
        item = items[idx]
        while True:
            _render(item, n, len(pick))
            try:
                key = _getkey("  [f]lag [p]ass [a]mbig [s]kip (q=quit) > ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                key = "q"
            if key == "q":
                break
            if key in ("f", "p", "a", "s"):
                _append(second_path, {"idx": idx,
                                      "label": {"f": "flag", "p": "pass",
                                                "a": "ambiguous", "s": "skip"}[key]})
                break
        if key == "q":
            break

    second = {r["idx"]: r["label"] for r in _read(second_path)} if second_path.exists() else {}
    both = [i for i in second if i in first]
    if both:
        agree = sum(1 for i in both if first[i]["label"] == second[i])
        print(f"\nself-agreement: {agree}/{len(both)} = {agree / len(both):.0%}")
        print("Report this next to the corpus. A labeller who cannot reproduce their own "
              "calls sets the ceiling on every number the corpus supports.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sample", help="stratified sample from a pool")
    s.add_argument("--pool", required=True)
    s.add_argument("--n", type=int, default=300)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--flagged-share", type=float, default=0.5,
                   help="fraction of the label budget spent on flagged writes")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_sample)

    l = sub.add_parser("label", help="blind labelling loop")
    l.add_argument("--session", required=True)
    l.set_defaults(fn=cmd_label)

    c = sub.add_parser("score", help="weighted precision and recall")
    c.add_argument("--session", required=True)
    c.set_defaults(fn=cmd_score)

    r = sub.add_parser("relabel", help="correct a label already written")
    r.add_argument("--session", required=True)
    r.add_argument("--position", type=int, help="1-based position from `list`")
    r.add_argument("--idx", type=int, help="the item's idx in the session")
    r.add_argument("--to", required=True, choices=["f", "p", "a", "s"])
    r.add_argument("--why", default="")
    r.set_defaults(fn=cmd_relabel)

    t = sub.add_parser("triage", help="label WHICH failure mode, over your flags")
    t.add_argument("--session", required=True)
    t.set_defaults(fn=cmd_triage)

    ls = sub.add_parser("list", help="show labels so far, with positions")
    ls.add_argument("--session", required=True)
    ls.add_argument("--tail", type=int, default=0, help="only the last N")
    ls.set_defaults(fn=cmd_list)

    a = sub.add_parser("agree", help="second pass for self-agreement")
    a.add_argument("--session", required=True)
    a.add_argument("--n", type=int, default=40)
    a.add_argument("--seed", type=int, default=0)
    a.set_defaults(fn=cmd_agree)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
