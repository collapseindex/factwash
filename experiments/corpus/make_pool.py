"""Build a pool of candidate memory writes from conversations this project did not write.

The point is provenance. The 44-write corpus used sources written here, so both halves of
every pair are ours. Here the SOURCE is external and only the extraction is ours, which is
the most independence obtainable given that no public corpus of real memory writes exists
at usable scale (MemGPT's traces yield 13).

Sources:

  enron      real workplace email, and the one that works. People forward, quote,
             paraphrase, hedge and correct each other constantly, which is the entire
             failure surface. Free, public, standard in NLP. Selection is STRUCTURAL
             (does this message carry quoted or forwarded content) and never lexical,
             because filtering on hedge vocabulary would build a pool out of exactly
             what the lexicon already sees. Contains real PII: see load_enron.
  msc        multi-session chat from the MemGPT traces. TRIED AND REJECTED; kept only so
             the negative result is on the record. Two independent reasons, both fatal:

             1. Feeding whole exchanges makes the extractor refuse. MSC is persona
                roleplay where the assistant owns a dog and attends concerts, so a current
                model breaks character to correct it. A 249-write pilot came back 58%
                UNCHECKABLE with "memories" like "I should clarify that as an AI, I don't
                actually have a dog". The 9% flag rate over that measured nothing.
             2. Restricting to user turns removes the persona problem and leaves nothing.
                100% of the 229 usable user turns are recall probes -- "remember that time
                we talked about X? What was Y?" -- because these traces are a memory
                BENCHMARK, not a conversation corpus. There are no fact statements to
                store.

             Cost of finding this out: $0.05. Cost of not finding it out: a 300-item
             corpus of refusal boilerplate with a precision figure attached.

Extraction uses mem0's own prompt by default, so the writes are the ones a real memory
system would produce rather than ones chosen to be catchable.

Metered, resumable, hard-capped, same as every other paid script here.

    python experiments/corpus/make_pool.py --source enron --n 400 --budget 0.60
    python experiments/corpus/make_pool.py --source enron --n 20 --budget 0 --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))

from runlog import Budget, BudgetExceeded, RunLog, price_call     # noqa: E402

EXTERNAL = ROOT / "data" / "external"
POOL_DIR = ROOT / "data" / "corpus"

# Deliberately close to what a memory system actually asks for. A prompt written to
# produce catchable failures would make the corpus a self-portrait.
EXTRACT_SYSTEM = """\
You maintain a long-term memory store for an assistant. Read the conversation and write \
the durable facts worth remembering about the user and their situation.

Write each memory on its own line, as a standalone statement that will still make sense \
months from now when the conversation is gone. Be contextually rich and specific.

Output only the memory lines. No preamble, no numbering, no commentary. If nothing is \
worth storing, output NOTHING."""

MAX_TOKENS = 400


def load_msc(limit: int, user_only: bool = True):
    """Real user turns from the MemGPT MSC traces.

    USER TURNS ONLY, by default, and that is not a detail. The first pilot fed whole
    exchanges and the extractor spent most of its output refusing: MSC is persona
    roleplay where the assistant claims to own a dog and attend concerts, so a current
    model breaks character to correct it. 58% of the resulting pool came back UNCHECKABLE
    and the "memories" were lines like "I should clarify that as an AI, I don't actually
    have a dog". A flag rate computed over that measures nothing.

    The user's own statements carry no persona to object to, and they are the half a
    memory store is actually about.
    """
    path = EXTERNAL / "memgpt_msc_full.jsonl"
    if not path.is_file():
        print(f"missing {path}; run experiments/external/fetch.py", file=sys.stderr)
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        turns = json.loads(line)
        parts = []
        for t in turns:
            role, content = t.get("role"), (t.get("content") or "")
            if role == "user":
                # Only real user turns. The trace wraps system_alert, login and heartbeat
                # events in the same {"type": ..., "message": ...} envelope, and matching
                # on "message" alone pulled "You have 50 prior messages with the user..."
                # into the source as if the user had said it.
                if '"type": "user_message"' not in content:
                    continue
                m = re.search(r'"message":\s*"(.*?)",\s*"time"', content, re.DOTALL)
                if m:
                    parts.append("User: " + m.group(1))
            elif role == "assistant" and not user_only:
                fc = t.get("function_call") or {}
                if fc.get("name") == "send_message":
                    try:
                        parts.append("Assistant: " + json.loads(fc["arguments"])["message"])
                    except Exception:
                        pass
        # A single exchange carries almost nothing to lose; require some substance.
        if len(parts) >= 1 and sum(len(p) for p in parts) > 120:
            out.append({"origin": "msc", "source": "\n".join(parts)})
        if len(out) >= limit:
            break
    return out


# --- Enron ------------------------------------------------------------------------------
# Structural markers of a RELAY: this message carries someone else's words. Deliberately
# NOT lexical. Selecting on hedge or attribution vocabulary would build a pool out of the
# things the lexicon already sees, and the resulting recall would be an artefact of the
# filter rather than a property of the tool. These match email plumbing instead.
_RELAY_MARKERS = (
    "-----original message-----", "-----forwarded", "---------------------- forwarded",
    "> -----", "wrote:", "forwarded by",
)
_QUOTE_LINE = re.compile(r"^\s*>", re.MULTILINE)
_HEADER_BLOCK = re.compile(
    r"^(from|to|cc|bcc|sent|date|subject|message-id|mime-version|content-type|"
    r"content-transfer-encoding|x-[\w-]+)\s*:.*$", re.IGNORECASE | re.MULTILINE)
# Pure PII with no task value. Names stay: they are what the claims are ABOUT, and
# stripping them would make relayed attribution unreadable. Addresses and phone numbers
# carry nothing the extractor needs.
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}(?!\d)")
_DISCLAIMER = re.compile(
    r"(this (e-?mail|message).{0,80}(confidential|privileged)|"
    r"if you (have received|are not the intended)).*", re.IGNORECASE | re.DOTALL)


def _clean_email(body: str) -> str:
    body = _DISCLAIMER.sub("", body)
    body = _HEADER_BLOCK.sub("", body)
    body = _EMAIL_RE.sub("[email]", body)
    body = _PHONE_RE.sub("[phone]", body)
    body = re.sub(r"^\s*>+\s?", "", body, flags=re.MULTILINE)   # unwrap quote carets
    body = re.sub(r"\n{3,}", "\n\n", body)
    return "\n".join(l.rstrip() for l in body.splitlines() if l.strip()).strip()


def load_enron(limit: int, archive: str | None = None, min_chars: int = 300,
               max_chars: int = 4000):
    """Enron email threads that relay someone else's words.

    Real workplace mail is the closest public match to the deployment domain: people
    forward, quote, paraphrase, hedge, and correct each other constantly, which is the
    entire failure surface. MSC had none of that (see above).

    Streams straight out of the .tar.gz -- no 1.5 GB extraction. Point --enron at the
    archive, or at an already-extracted maildir.

    SELECTION IS STRUCTURAL, NOT LEXICAL, and that is the load-bearing choice. A pool
    filtered by hedge or attribution vocabulary would contain exactly the phrasings the
    lexicon already knows, and the recall measured on it would be a property of the filter.
    Messages are kept because they carry quoted or forwarded content, which is email
    plumbing and says nothing about wording.

    PII: this corpus is real mail from real people. Addresses and phone numbers are masked
    here; NAMES ARE KEPT, because they are what the claims are about and relayed
    attribution is unreadable without them. The pool lands in data/ (gitignored). Do not
    commit it, and redact before publishing any excerpt.
    """
    import email
    import tarfile

    path = Path(archive) if archive else (EXTERNAL / "enron_mail.tar.gz")
    out, seen = [], set()

    def consider(raw: bytes):
        if len(out) >= limit:
            return
        try:
            msg = email.message_from_bytes(raw)
        except Exception:
            return
        if msg.is_multipart():
            parts = [p for p in msg.walk() if p.get_content_type() == "text/plain"]
            body = "".join(p.get_payload(decode=False) or "" for p in parts)
        else:
            body = msg.get_payload(decode=False) or ""
        if not isinstance(body, str):
            return
        low = body.lower()
        relay = any(m in low for m in _RELAY_MARKERS) or len(_QUOTE_LINE.findall(body)) >= 2
        if not relay:
            return
        text = _clean_email(body)
        if not (min_chars <= len(text) <= max_chars):
            return
        key = text[:200]
        if key in seen:
            return                          # Enron is full of near-duplicate forwards
        seen.add(key)
        out.append({"origin": "enron", "source": text,
                    "msgid": (msg.get("Message-ID") or "").strip()})

    if path.is_dir():
        for p in path.rglob("*"):
            if p.is_file():
                consider(p.read_bytes())
            if len(out) >= limit:
                break
    elif path.is_file():
        with tarfile.open(path, "r:gz") as tar:
            for member in tar:
                if not member.isfile():
                    continue
                fh = tar.extractfile(member)
                if fh is None:
                    continue
                consider(fh.read())
                if len(out) >= limit:
                    break
    else:
        print(f"missing {path}: download enron_mail_20150507.tar.gz from "
              f"https://www.cs.cmu.edu/~enron/ into data/external/", file=sys.stderr)
    return out


SOURCES = {"msc": load_msc, "enron": load_enron}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=sorted(SOURCES), default="msc")
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--model", default="claude-haiku-4-5")
    ap.add_argument("--budget", type=float, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--resume", type=Path)
    ap.add_argument("--enron", help="path to enron_mail.tar.gz or an extracted maildir")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    convs = (load_enron(args.n, args.enron) if args.source == "enron"
             else SOURCES[args.source](args.n))
    if not convs:
        print("no conversations loaded", file=sys.stderr)
        return 1
    print(f"{len(convs)} external conversations from '{args.source}'")

    client = None
    if not args.dry_run:
        try:
            import anthropic
        except ImportError:
            print("needs: pip install anthropic", file=sys.stderr)
            return 1
        client = anthropic.Anthropic()

    budget = Budget(cap_usd=args.budget)
    log = RunLog(operation=f"pool_{args.source}", model=args.model,
                 params=f"n{len(convs)}", seed=args.seed, resume_path=args.resume)
    budget.spent_usd = log.prior_spend_usd

    written = 0
    try:
        for i, conv in enumerate(convs):
            item_id = f"{args.source}|{i}"
            if log.is_done(item_id):
                continue
            if args.dry_run:
                log.append({"id": item_id, "origin": conv["origin"],
                            "source": conv["source"], "memory": "", "dry_run": True,
                            "cost_usd": 0.0})
                continue
            budget.check(0.004)
            resp = client.messages.create(
                model=args.model, max_tokens=MAX_TOKENS, system=EXTRACT_SYSTEM,
                messages=[{"role": "user", "content": conv["source"]}],
            )
            text = "".join(b.text for b in resp.content
                           if getattr(b, "type", "") == "text").strip()
            usage = resp.usage
            cost = price_call(args.model, usage.input_tokens, usage.output_tokens,
                              raw=usage.model_dump() if hasattr(usage, "model_dump") else None)
            budget.record(cost.usd)
            # One row per memory LINE: the unit being labelled is a single write.
            for j, mem in enumerate(l.strip("-* ").strip()
                                    for l in text.splitlines() if l.strip()):
                if not mem:
                    continue
                log.append({"id": f"{item_id}|{j}", "origin": conv["origin"],
                            "source": conv["source"], "memory": mem,
                            "cost_usd": cost.usd if j == 0 else 0.0})
                written += 1
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(convs)}  {written} writes  ${budget.spent_usd:.4f}")
    except BudgetExceeded as e:
        print(f"\nSTOPPED ON BUDGET: {e}\nresume: --resume {log.path}", file=sys.stderr)
    except KeyboardInterrupt:
        print(f"\ninterrupted; resume: --resume {log.path}", file=sys.stderr)
    finally:
        log.close()

    POOL_DIR.mkdir(parents=True, exist_ok=True)
    pool = POOL_DIR / f"pool_{args.source}_s{args.seed}.jsonl"
    rows = [r for r in log.records() if r.get("memory")]
    pool.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                    encoding="utf-8")
    print(f"\n{len(rows)} candidate writes -> {pool}")
    print(f"spend: ${budget.spent_usd:.4f}")
    print(f"next: python experiments/corpus/label.py sample --pool {pool} --n 300")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
