# Backend survey for the broadening (2026-08-03)

Same method as `refchecker_port_verdict.md`: shallow clone, read the dep tree and the
license, decide dependency vs port vs pattern-mine. TWSS's constitution stays
`dependencies = []`; everything below is an optional extra or a read.

**Decision (2026-08-03, keep-it-light):** quantulum3 adopted (`twss[units]`); the torch
backends are SHELVED, not chosen-between. When ADDED lands it goes through the existing
witness pattern first (zero new deps); MiniCheck/LettuceDetect stay documented here as
the local-model options if anyone ever needs offline ADDED.

## MiniCheck (Apache-2.0) - ADDED backend candidate, claim-level

- 1,851 lines across 7 files; the whole codebase is readable in an hour.
- API: `MiniCheck(model_name).score(docs, claims) -> List[float]`; scalar support
  probability per claim, threshold in our code, not theirs.
- Deps: torch, transformers, datasets, nltk, pandas, numpy, openai. Heavy, so it lives
  behind an extra (`twss[added-minicheck]`), never in the default install.
- Local models: flan-t5-large (770M) via HF, or ollama. No API key required = fits the
  local-by-default rule.
- Caveat: returns probabilities without evidence spans. Fine for a verdict, thin for a
  report; pairs with sentence-ID localization (see RefChecker port note) to get spans.

## LettuceDetect (MIT) - ADDED backend candidate, span-level

- 20,862 lines, 115 files; a framework, not a module. Dependency, never a port.
- Modern pins (torch>=2.6, transformers>=4.48), actively maintained, ModernBERT-based,
  TinyLettuce variants down to 17M params.
- Returns token/span-level predictions = evidence spans for free, which is exactly what
  Change.evidence wants.
- Pulls `rag-fact-checker` + openai transitively. Same treatment: `twss[added-lettuce]`.

## quantulum3 (MIT) - units/quantity parsing for the numeric pack

- Deps: `inflect` + `num2words` ONLY. Near-free to adopt; the one candidate that could
  sit close to the default install (still an extra, `twss[units]`, to keep zero-dep true).
- Parses values, units, ranges, uncertainties, spelled-out numbers, with character spans.
- Overlap check before adopting: claims.py already extracts values/money. quantulum3 adds
  UNITS and ranges, i.e. a preserve-units / unit-changed check, not a replacement for
  `numbers()`.
- **ADOPTED 2026-08-03** as the `twss[units]` extra; detector lives in `transform.py`
  (value-keyed, transform-layer only, gate untouched). See CHANGELOG "Unreleased".

## Loki / OpenFactVerification (MIT) - patterns only

- Dep tree disqualifies it as a dependency: flask, opencv-python, playwright,
  playwright_stealth, pandas. It is a web-retrieval fact-checking app.
- Worth reading: one-class-per-stage pipeline (decompose -> checkworthy -> query ->
  retrieve -> verify) as a shape reference for the eventual multi-stage ADDED path.
  Drop the retrieval half; TWSS checks against a supplied source, not the web.

## Integration contract (decided, not yet built)

The ADDED backend mirrors the existing witness pattern (optional callable, validated
output, policy stays in code):

    added_backend(source: str, claim: str) -> {"supported": bool | None,
                                               "evidence": list[str]}

- `None` means the backend could not evaluate -> UNCHECKABLE, never PASS.
- Evidence strings are validated against the source before use, exactly like witness
  markers; a backend that cites text not in the source is discarded.
- Both MiniCheck (threshold the scalar, no spans) and LettuceDetect (spans native) fit
  behind this contract; which ships first is a product call, not an architecture one.
- Backends install via extras; the default package keeps `dependencies = []`.
