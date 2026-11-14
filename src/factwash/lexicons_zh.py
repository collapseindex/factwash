"""Chinese stance lexicons (experimental, lexicon-only).

This module adds Chinese marker tuples for the same three signals the English
lexicons track: negation, attribution, and hedging. It contains **no logic** —
callers that already use the English tuples can decide whether to extend their
checks with the Chinese ones.

Why a separate module instead of extending the English tuples: the two
languages mark stance differently. English leans on modal auxiliaries
("might", "may", "reportedly"); Chinese leans on sentence-final particles,
ellipsis, and short hedges ("可能", "好像", "说不定"). Mixing them into one
tuple hides that difference and makes it hard to audit either list.

Known boundaries (please read before using):

1. ``我觉得`` is listed under hedges because it usually softens a claim
   ("我觉得他可能有点累"), but it can also mark a topic shift or a contrast.
   A context-free hit may be a false positive.
2. ``肯定`` / ``一定`` are NOT listed here on purpose: they are intensity
   markers, not discourse noise. Do not add them to a "content noise" list.
3. Quoted spans should be stripped before matching (``「」``, ``“”``, ``""``):
   a word inside quotes is mentioned, not asserted.

Minimal examples (no real conversation, hand-written):

    source: 有人说那个补丁可能有问题，我不确定。
    output: 那个补丁有问题。
    expect: attribution dropped + hedge dropped

    source: 我今天没吃早饭。
    output: 他今天吃了早饭。
    expect: polarity changed

    source: 可能下雨。
    output: 我猜今天可能下雨。
    expect: no flag (hedge preserved)
"""

NEGATION_ZH = (
    "没", "没有", "不", "别", "未", "并非", "不是", "从来没", "算不上", "谈不上",
)

ATTRIBUTION_ZH = (
    "听说", "有人说", "据说", "网上说", "他告诉我", "她说", "报告里", "转的",
    "群里说", "微信里说", "某人说",
)

HEDGE_ZH = (
    "可能", "好像", "大概", "也许", "说不定", "不一定", "我猜", "记不清",
    "不确定", "估计", "似乎", "不太确定", "我觉得",
)

STRENGTH_ZH = (
    "肯定", "一定", "绝对", "必然", "从来", "一直", "保证", "承认",
)

__all__ = ["NEGATION_ZH", "ATTRIBUTION_ZH", "HEDGE_ZH", "STRENGTH_ZH"]
