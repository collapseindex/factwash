# Superseded runs

These are real runs, kept and published deliberately. They are **not** pooled into the
analysis, and `experiments/two_cell_analyse.py` cannot reach them: it globs only the top
level of `data/raw/`.

They were produced before a bug in the blind reader's parser was found. The judge was
asked for JSON and, whenever a stored memory carried two stance cues, returned this:

```
{"presented_as": "qualified", "cue": "may have", "unconfirmed rumor from third party"}
```

which is not valid JSON. `json.loads` raised, the verdict was stored as `null`, and the
scorer counted it as "standing did not survive". About 6% of trials were affected, and
they were the least ambiguous ones, so the loss was not random with respect to the
outcome. On this data the pooled field-over-prose advantage read **+9.3 points**; the
same design after the fix gives **+4.0**.

They are published so that claim is checkable rather than asserted. Pooling them with the
post-fix runs would mix two measurement regimes, which is why they live here instead.

Note that rows in these files lack the `blind_raw` and `blind_parsed_how` fields. Their
absence is the reason the bug took a reproduction run to diagnose, and adding them was
part of the fix.

| file | model | note |
|---|---|---|
| `20260804_163652_twocell_claude-haiku-4-5_n10x3_s0.jsonl` | Haiku 4.5 | first two-cell design, no compression pressure; the compressor expanded a 60-char note to 90 chars, so nothing could be lost |
| `20260804_164025_twocellpress_claude-haiku-4-5_n10x4x2_s0.jsonl` | Haiku 4.5 | first pressure sweep, pre-fix parser |
| `20260804_164622_twocellpress_claude-haiku-4-5_n10x4x6_s100.jsonl` | Haiku 4.5 | partial, stopped when the bug was found |
| `20260804_164626_twocellpress_claude-sonnet-4-5_n10x4x4_s100.jsonl` | Sonnet 4.5 | partial, stopped when the bug was found |
