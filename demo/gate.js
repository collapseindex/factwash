/* Factwash gate, ported from src/factwash/{lexicons,claims,checks,report}.py.
   Runs in node (for the cross-check against Python) and in the browser unchanged. */
(function (root) {
  "use strict";

  // --- lexicons.py, verbatim -------------------------------------------------------
  // GENERATED from src/factwash/lexicons.py by demo/build.py -- do not hand-edit.
  var HEDGE = ["probably", "might", "may ", "maybe", "possibly", "perhaps", "seems", "appears", "reportedly", "allegedly", "rumor", "unverified", "unconfirmed", "not verified", "to be verified", "unreliable", "not reconciled", "uncertain", "alleged", "purported", "i think", "i believe", "iirc", "if i recall", "supposedly", "sounds like", "heard that", "heard from", "not sure", "could be", "not confirmed", "yet to be confirmed", "not been verified", "apparently", "evidently", "ostensibly", "presumably", "arguably", "suggests", "suggested", "indicates that", "may have", "might have", "believed to", "thought to", "understood to", "expected to", "pending confirmation", "not established", "not yet established", "subject to confirmation", "to be confirmed", "tbc", "unclear whether", "some indication", "early signs", "if true", "assuming", "suggest", "indicate", "likely", "considered to", "assume", "believed that"];
  var ATTRIB = ["said", "says", "claim", "note", "noted", "record", "mention", "told", "reportedly", "user:", "asked", "message", "according", "stated that", "rumor", "heard that", "heard from", "word is", "someone", "fyi", "reported", "relayed", "passed on", "secondhand", "second-hand", "grapevine", "chatter", "as per", "per the", "from the team", "i'm told", "we're told", "was told", "hearsay", "attributed to", "credited to", "cites", "cited", "quoting", "paraphrasing", "say", "added", "wrote", "agreed"];
  var HEDGE_IN_MEMORY = ["probably", "might", "may ", "maybe", "possibly", "perhaps", "seems", "appears", "reportedly", "allegedly", "rumor", "unverified", "unconfirmed", "not verified", "to be verified", "unreliable", "not reconciled", "uncertain", "alleged", "purported", "i think", "i believe", "iirc", "if i recall", "supposedly", "sounds like", "heard that", "heard from", "not sure", "could be", "not confirmed", "yet to be confirmed", "not been verified", "apparently", "evidently", "ostensibly", "presumably", "arguably", "suggests", "suggested", "indicates that", "may have", "might have", "believed to", "thought to", "understood to", "expected to", "pending confirmation", "not established", "not yet established", "subject to confirmation", "to be confirmed", "tbc", "unclear whether", "some indication", "early signs", "if true", "assuming", "suggest", "indicate", "likely", "considered to", "assume", "believed that", "state that", "states that", "stating", "claims", "claimed", "claiming", "notes that", "noting", "mentions", "mentioning", "says that", "saying", "tells", "telling", "recounts", "unverified", "uncorroborated", "alleges", "alleging", "say", "report"];
  var ATTRIB_IN_MEMORY = ["said", "says", "claim", "note", "noted", "record", "mention", "told", "reportedly", "user:", "asked", "message", "according", "stated that", "rumor", "heard that", "heard from", "word is", "someone", "fyi", "reported", "relayed", "passed on", "secondhand", "second-hand", "grapevine", "chatter", "as per", "per the", "from the team", "i'm told", "we're told", "was told", "hearsay", "attributed to", "credited to", "cites", "cited", "quoting", "paraphrasing", "say", "added", "wrote", "agreed", "state that", "states that", "stating", "claims", "claimed", "claiming", "notes that", "noting", "mentions", "mentioning", "says that", "saying", "tells", "telling", "recounts", "unverified", "uncorroborated", "alleges", "alleging", "say", "report"];
  var EVIDENTIAL = ["reportedly", "allegedly", "rumor", "supposedly", "i heard", "someone", "word is"];
  var AGGREGATE_CUES = ["total", "in all", "altogether", "overall", "comes to", "came to", "sum", "adds up", "grand total", "combined", "average"];
  var NEGATION_PATTERN = "\\b(?:not|never|no|none|nobody|nothing|nowhere|neither|nor|cannot|without|denied|declines?|declined|rejects?|rejected|refuses?|refused|revoked|lacks?|excluded|prohibited|forbidden|disallowed)\\b|n't\\b|\\b(?:fail(?:s|ed|ure|ing)?|unable|lacking)\\b";
  var CONDITIONAL_PATTERN = "\\b(?:if|unless|provided that|as long as|in case|only when|only if|contingent on|conditional on|depending on|assuming(?!\\s+(?:command|control|office|power|responsibility|the\\s+(?:role|position|presidency|throne)))|in the event that|so long as)\\b";
  var INTERROGATIVE_IF = "\\b(?:see|determine|test|tested|check|checked|investigate|investigated|examine|examined|assess|assessed|ask|asked|know|wonder|evaluate|evaluated|verify|verified|establish)\\b[^.]{0,20}?\\bif\\b|\\bif\\s+any\\b";
  var TEMPORAL_PATTERN = "\\b(?:19|20)\\d\\d\\b|\\bq[1-4]\\b|\\b(?:january|february|march|april|june|july|august|september|october|november|december)\\b|\\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\\b|\\b(?:yesterday|today|tomorrow|tonight)\\b|\\b(?:last|next|this|past|previous|coming)\\s+(?:night|week|month|quarter|year|morning|afternoon|evening|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\\b|\\b(?:back\\s+in|as\\s+of|at\\s+the\\s+time|used\\s+to|formerly|previously|historically|since|ago|earlier|no\\s+longer|at\\s+that\\s+point|at\\s+one\\s+point)\\b";
  var COMPLETENESS_MARKERS = ["incomplete", "partial", "truncated", "subset", "some of", "not all"];
  var STOPWORDS = new Set(["a", "all", "also", "am", "an", "and", "any", "are", "as", "at", "be", "been", "being", "both", "but", "by", "can", "could", "did", "do", "does", "done", "each", "few", "for", "from", "get", "got", "had", "has", "have", "he", "her", "here", "him", "how", "i", "if", "in", "is", "it", "its", "just", "let", "lets", "me", "more", "most", "must", "my", "no", "not", "now", "of", "on", "only", "or", "other", "our", "own", "same", "shall", "she", "should", "so", "some", "such", "than", "that", "the", "their", "them", "then", "there", "these", "they", "this", "those", "to", "too", "us", "very", "was", "we", "were", "what", "when", "where", "which", "who", "whom", "why", "will", "with", "would", "yes", "you", "your"]);

  // --- claims.py -------------------------------------------------------------------
  var MIN_SHARED = 2, MIN_CONTAINMENT = 0.25, VALUE_TOL = 0.005;
  var SENTENCE_SPLIT = /(?<=[.!?])\s+|\n+/;
  var TOKEN_RE = /[a-z0-9$€£][\w.$€£%,-]*/g;
  var NUMBER_RE = /(?:([$€£]\s?))?(\d(?:[\d,]*\d)?(?:\.\d+)?)/g;
  var YEAR_RE = /^(19|20)\d\d$/;
  var ROLE_RE = /^[ \t]*(user|assistant|system|tool)[ \t]*:[ \t]*/gim;

  function stripRoles(t) { return t.replace(ROLE_RE, ""); }
  function sentences(t) {
    return t.split(SENTENCE_SPLIT).map(function (s) { return s.trim(); }).filter(Boolean);
  }
  function isQuestion(s) { return /\?$/.test(s.replace(/\s+$/, "")); }

  function contentWords(text) {
    var out = new Set(), m, low = text.toLowerCase();
    TOKEN_RE.lastIndex = 0;
    while ((m = TOKEN_RE.exec(low)) !== null) {
      var tok = m[0].replace(/^[.,-]+|[.,-]+$/g, "");
      if (!tok) continue;
      if (tok.length < 2 && !/^\d+$/.test(tok)) continue;
      if (STOPWORDS.has(tok)) continue;
      out.add(tok);
    }
    return out;
  }

  function numbersWithPos(text) {
    var out = [], m;
    NUMBER_RE.lastIndex = 0;
    while ((m = NUMBER_RE.exec(text)) !== null) {
      var start = m.index, end = start + m[0].length;
      var prev = start > 0 ? text[start - 1] : "";
      var next = end < text.length ? text[end] : "";
      if (/[a-zA-Z0-9]/.test(prev) || ".-/".indexOf(prev) !== -1) continue;
      if (/[a-zA-Z]/.test(next)) continue;
      if ("-/".indexOf(next) !== -1 && end + 1 < text.length && /\d/.test(text[end + 1])) continue;
      var num = m[2], isMoney = !!m[1];
      if (!isMoney && YEAR_RE.test(num)) continue;
      var value = parseFloat(num.replace(/,/g, ""));
      if (isNaN(value)) continue;
      out.push({ raw: m[0].trim(), value: value, isMoney: isMoney, pos: start });
    }
    return out;
  }

  function intersect(a, b) {
    var out = new Set();
    a.forEach(function (x) { if (b.has(x)) out.add(x); });
    return out;
  }

  // neighbors=false narrows to the matched sentence alone. Hedges float across sentence
  // boundaries; attribution and negation are clause-attached. See checks.py.
  function matchSourceWindow(memSentence, srcSentences, neighbors) {
    if (neighbors === undefined) neighbors = true;
    var memWords = contentWords(memSentence);
    if (memWords.size < MIN_SHARED) return null;
    var bestI = null, bestScore = 0;
    for (var i = 0; i < srcSentences.length; i++) {
      var srcWords = contentWords(srcSentences[i]);
      var shared = intersect(memWords, srcWords);
      if (shared.size < MIN_SHARED) continue;
      var score = shared.size / Math.min(memWords.size, srcWords.size);
      if (score > bestScore) { bestI = i; bestScore = score; }
    }
    if (bestI === null || bestScore < MIN_CONTAINMENT) return null;
    if (!neighbors) return srcSentences[bestI];
    var lo = Math.max(0, bestI - 1), hi = Math.min(srcSentences.length, bestI + 2);
    return srcSentences.slice(lo, hi).join(" ");
  }

  // Ported from claims.matching_source_indices: {index: score} for every source sentence
  // that matches the claim. Supersession needs the scores, not just the best match.
  function matchingSourceIndices(memSentence, srcSentences) {
    var memWords = contentWords(memSentence), out = {};
    if (memWords.size < MIN_SHARED) return out;
    for (var i = 0; i < srcSentences.length; i++) {
      var srcWords = contentWords(srcSentences[i]);
      var shared = intersect(memWords, srcWords);
      if (shared.size < MIN_SHARED) continue;
      var score = shared.size / Math.min(memWords.size, srcWords.size);
      if (score >= MIN_CONTAINMENT) out[i] = score;
    }
    return out;
  }

  // --- checks.py -------------------------------------------------------------------
  var CITATIONS = {
    BRITTLE: "Reclaim Sec. 4, source-token test",
    TRUNCATED: "Reclaim Sec. 7, recompute certificate + completeness tag",
    MANUFACTURED_CONFIDENCE: "Manufactured Confidence App. E, dehedged()",
    LAUNDERED: "Manufactured Confidence App. E, laundering metric",
    POLARITY_CHANGED: "Factwash: closed-class negation, not from the papers",
    CONDITION_DROPPED: "Factwash: closed-class conditionals, not from the papers",
    TEMPORAL_SCOPE_DROPPED: "Factwash: bounded time expressions, not from the papers"
  };
  function trunc(t, n) {
    n = n || 90; t = t.split(/\s+/).join(" ");
    return t.length <= n ? t : t.slice(0, n - 3) + "...";
  }
  function fmt(vals) { return "[" + vals.map(function (v) { return String(v); }).join(", ") + "]"; }

  function conclusions(memory) {
    var out = [];
    sentences(memory).forEach(function (sent) {
      if (isQuestion(sent)) return;
      var low = sent.toLowerCase(), cuePos = -1;
      AGGREGATE_CUES.forEach(function (c) {
        var idx = low.indexOf(c);
        if (idx !== -1 && (cuePos === -1 || idx < cuePos)) cuePos = idx;
      });
      if (cuePos < 0) return;
      var best = null, bestDist = null;
      numbersWithPos(sent).forEach(function (n) {
        var dist = Math.abs(n.pos - cuePos) - (n.isMoney ? 1000 : 0);
        if (best === null || dist < bestDist) { best = n; bestDist = dist; }
      });
      if (best) out.push({ sentence: sent, target: best });
    });
    return out;
  }

  function derivations(source, memory) {
    var srcNums = numbersWithPos(source), memNums = numbersWithPos(memory), out = [];
    conclusions(memory).forEach(function (c) {
      var claimed = c.target.value;
      var inputs = srcNums.filter(function (n) { return Math.abs(n.value - claimed) > VALUE_TOL; });
      var distinctSet = {};
      inputs.forEach(function (n) { distinctSet[Math.round(n.value * 100) / 100] = true; });
      var distinct = Object.keys(distinctSet).map(Number).sort(function (a, b) { return a - b; });
      var memVals = {};
      memNums.forEach(function (n) {
        if (Math.abs(n.value - claimed) > VALUE_TOL) memVals[Math.round(n.value * 100) / 100] = true;
      });
      var retained = distinct.filter(function (v) { return memVals[v]; });
      var missing = distinct.filter(function (v) { return !memVals[v]; });
      out.push({ sentence: c.sentence, claimed: claimed, inputs: inputs,
                 distinct: distinct, retained: retained, missing: missing });
    });
    return out;
  }

  function checkBrittle(source, memory) {
    var ders = derivations(source, memory);
    if (!ders.length) return { check: "BRITTLE", status: "n/a", flags: [], note: "no derived conclusion (aggregate cue + value) in memory" };
    var applicable = ders.filter(function (d) { return d.distinct.length >= 2; });
    if (!applicable.length) return { check: "BRITTLE", status: "n/a", flags: [], note: "conclusion present but source has no re-derivation values" };
    var flags = [], status = "pass";
    applicable.forEach(function (d) {
      if (!d.retained.length) {
        status = "fail";
        flags.push({ name: "BRITTLE", severity: "fail", citation: CITATIONS.BRITTLE,
          evidence: "conclusion kept ('" + trunc(d.sentence) + "') but none of the source values " + fmt(d.distinct) + " are retained" });
      } else if (d.missing.length) {
        if (status !== "fail") status = "warn";
        flags.push({ name: "BRITTLE", severity: "warn", citation: CITATIONS.BRITTLE,
          evidence: "partial basis for '" + trunc(d.sentence) + "': retained " + fmt(d.retained) + ", missing " + fmt(d.missing) });
      }
    });
    return { check: "BRITTLE", status: status, flags: flags, note: "" };
  }

  function hasCompletenessTag(memory) {
    var low = memory.toLowerCase();
    if (/\b\d+\s+of\s+\d+\b/.test(low)) return true;
    return COMPLETENESS_MARKERS.some(function (m) { return low.indexOf(m) !== -1; });
  }

  function checkTruncated(source, memory) {
    var ders = derivations(source, memory);
    if (!ders.length) return { check: "TRUNCATED", status: "n/a", flags: [], note: "no derived conclusion in memory" };
    var flags = [], status = "pass", certifiedAny = false;
    ders.forEach(function (d) {
      var certified = null;
      var candidates = [d.inputs, d.inputs.filter(function (n) { return n.isMoney; })];
      for (var i = 0; i < candidates.length; i++) {
        var c = candidates[i];
        if (c.length >= 2) {
          var s = c.reduce(function (a, n) { return a + n.value; }, 0);
          if (Math.abs(s - d.claimed) <= 0.01) { certified = c; break; }
        }
      }
      if (!certified) return;
      certifiedAny = true;
      if (!d.missing.length) {
        flags.push({ name: "TRUNCATED", severity: "info", citation: CITATIONS.TRUNCATED,
          evidence: "certificate: recomputed " + d.claimed + " from " + d.distinct.length + " of " + d.distinct.length + " retained values" });
      } else if (hasCompletenessTag(memory)) {
        if (status !== "fail") status = "warn";
        flags.push({ name: "TRUNCATED", severity: "warn", citation: CITATIONS.TRUNCATED,
          evidence: "incomplete but tagged: missing " + fmt(d.missing) + " behind a completeness marker" });
      } else {
        status = "fail";
        var retainedSum = certified.filter(function (n) {
          return d.retained.indexOf(Math.round(n.value * 100) / 100) !== -1;
        }).reduce(function (a, n) { return a + n.value; }, 0);
        flags.push({ name: "TRUNCATED", severity: "fail", citation: CITATIONS.TRUNCATED,
          evidence: "memory claims " + d.claimed + " but retained values recompute to " + retainedSum + "; completeness tag missing (add 'k of N items')" });
      }
    });
    if (!certifiedAny) return { check: "TRUNCATED", status: "n/a", flags: [], note: "no recomputable derivation (source values do not recompute the claimed total)" };
    return { check: "TRUNCATED", status: status, flags: flags, note: "" };
  }

  function stancePairs(source, memory, neighbors) {
    if (neighbors === undefined) neighbors = true;
    var srcSents = sentences(source), out = [];
    sentences(memory).forEach(function (sent) {
      if (isQuestion(sent)) return;
      var w = matchSourceWindow(sent, srcSents, neighbors);
      if (w !== null) out.push({ sentence: sent, window: w });
    });
    return out;
  }

  function stanceCheck(source, memory, name, sourceLex, memoryLex, label) {
    // LAUNDERED narrows to one sentence, MANUFACTURED_CONFIDENCE does not. See checks.py.
    var pairs = stancePairs(source, memory, name !== "LAUNDERED"), flags = [];
    if (!pairs.length) return { check: name, status: "n/a", flags: [], note: "no memory claim matched a source claim" };
    pairs.forEach(function (p) {
      var wLow = p.window.toLowerCase(), mLow = p.sentence.toLowerCase();
      var present = sourceLex.filter(function (t) { return wLow.indexOf(t) !== -1; });
      var kept = memoryLex.some(function (t) { return mLow.indexOf(t) !== -1; });
      if (present.length && !kept) {
        flags.push({
          name: name, severity: "fail", citation: CITATIONS[name],
          evidential: name === "MANUFACTURED_CONFIDENCE" && present.some(function (t) { return EVIDENTIAL.indexOf(t) !== -1; }),
          stripped: present,
          evidence: label + " [" + present.join(", ") + "] in source ('" + trunc(p.window) + "') " +
                    (name === "LAUNDERED" ? "dropped" : "stripped") + " in memory ('" + trunc(p.sentence) + "')"
        });
      }
    });
    return { check: name, status: flags.length ? "fail" : "pass", flags: flags, note: "" };
  }

  var NEG_RE = new RegExp(NEGATION_PATTERN, "gi");
  var COND_RE = new RegExp(CONDITIONAL_PATTERN, "gi");
  var TIME_RE = new RegExp(TEMPORAL_PATTERN, "gi");
  function findAll(re, text) {
    re.lastIndex = 0;
    var out = [], m;
    while ((m = re.exec(text)) !== null) { out.push(m[0]); if (m.index === re.lastIndex) re.lastIndex++; }
    return out;
  }

  // Ported from checks._superseded: a transcript can deny something and then retract the
  // denial, and only the last word counts. Narrow on purpose -- the later sentence must
  // carry no negation, come after, and match the claim at least as well as the denial.
  function superseded(memSentence, window, srcSents) {
    var here = srcSents.indexOf(window);
    if (here < 0) return false;
    var matches = matchingSourceIndices(memSentence, srcSents);
    var denialScore = matches[here] || 0;
    for (var k in matches) {
      var i = parseInt(k, 10);
      if (i > here && matches[k] >= denialScore && !findAll(NEG_RE, srcSents[i]).length) return true;
    }
    return false;
  }

  function checkPolarity(source, memory) {
    // Negation is clause-attached: single-sentence window, as in checks.py.
    var pairs = stancePairs(source, memory, false), flags = [];
    if (!pairs.length) return { check: "POLARITY_CHANGED", status: "n/a", flags: [], note: "no memory claim matched a source claim" };
    var memNeg = findAll(NEG_RE, memory);
    var srcSents = sentences(source);
    pairs.forEach(function (p) {
      var srcNeg = findAll(NEG_RE, p.window);
      if (srcNeg.length && superseded(p.sentence, p.window, srcSents)) return;
      if (srcNeg.length && !memNeg.length) {
        flags.push({ name: "POLARITY_CHANGED", severity: "fail", citation: CITATIONS.POLARITY_CHANGED,
          evidence: "source denied it, memory asserts it: source [" + srcNeg.join(", ") +
                    "] vs memory [] ('" + trunc(p.window) + "' -> '" + trunc(p.sentence) + "')" });
      }
    });
    return { check: "POLARITY_CHANGED", status: flags.length ? "fail" : "pass", flags: flags, note: "" };
  }

  // Ported from lexicons.conditionals_in: an "if" meaning "whether" is a complement, not
  // a condition. Only suppresses when "if" is the ONLY conditional matched.
  var INTERROG_IF_RE = new RegExp(INTERROGATIVE_IF, "i");
  function conditionalsIn(text) {
    var hits = findAll(COND_RE, text);
    if (hits.length && hits.every(function (h) { return h.toLowerCase() === "if"; })
        && INTERROG_IF_RE.test(text)) return [];
    return hits;
  }

  function checkCondition(source, memory) {
    var pairs = stancePairs(source, memory), flags = [];
    if (!pairs.length) return { check: "CONDITION_DROPPED", status: "n/a", flags: [], note: "no memory claim matched a source claim" };
    pairs.forEach(function (p) {
      var srcCond = conditionalsIn(p.window);
      if (srcCond.length && !conditionalsIn(p.sentence).length) {
        flags.push({ name: "CONDITION_DROPPED", severity: "fail", citation: CITATIONS.CONDITION_DROPPED,
          evidence: "condition [" + srcCond.join(", ") + "] in source ('" + trunc(p.window) +
                    "') dropped in memory ('" + trunc(p.sentence) + "'), storing it as unconditional" });
      }
    });
    return { check: "CONDITION_DROPPED", status: flags.length ? "fail" : "pass", flags: flags, note: "" };
  }

  function checkTemporal(source, memory) {
    var pairs = stancePairs(source, memory), flags = [];
    if (!pairs.length) return { check: "TEMPORAL_SCOPE_DROPPED", status: "n/a", flags: [], note: "no memory claim matched a source claim" };
    var memTimes = findAll(TIME_RE, memory);
    pairs.forEach(function (p) {
      var srcTimes = findAll(TIME_RE, p.window);
      if (srcTimes.length && !memTimes.length) {
        flags.push({ name: "TEMPORAL_SCOPE_DROPPED", severity: "warn", citation: CITATIONS.TEMPORAL_SCOPE_DROPPED,
          evidence: "source scoped this to [" + srcTimes.join(", ") + "] ('" + trunc(p.window) +
                    "') and the memory stores it undated ('" + trunc(p.sentence) + "'), so it will read as current later" });
      }
    });
    return { check: "TEMPORAL_SCOPE_DROPPED", status: flags.length ? "warn" : "pass", flags: flags, note: "" };
  }

  // --- report.py -------------------------------------------------------------------
  var REJECTING = ["BRITTLE", "TRUNCATED", "POLARITY_CHANGED"],
      REWRITING = ["MANUFACTURED_CONFIDENCE", "LAUNDERED", "CONDITION_DROPPED"];

  function check(source, memory) {
    var src = stripRoles(source);
    var outcomes = [
      checkBrittle(src, memory),
      checkTruncated(src, memory),
      stanceCheck(src, memory, "MANUFACTURED_CONFIDENCE", HEDGE, HEDGE_IN_MEMORY, "hedge"),
      stanceCheck(src, memory, "LAUNDERED", ATTRIB, ATTRIB_IN_MEMORY, "attribution"),
      checkPolarity(src, memory),
      checkCondition(src, memory),
      checkTemporal(src, memory)
    ];
    var failed = outcomes.filter(function (o) { return o.status === "fail"; }).map(function (o) { return o.check; });
    var verdict;
    // all-N/A is not a pass: nothing could be checked. Mirrors report.decide().
    if (outcomes.every(function (o) { return o.status === "n/a"; })) verdict = "UNCHECKABLE";
    else if (failed.some(function (f) { return REJECTING.indexOf(f) !== -1; })) verdict = "REJECT";
    else if (failed.some(function (f) { return REWRITING.indexOf(f) !== -1; })) verdict = "REWRITE";
    else if (outcomes.some(function (o) { return o.status === "warn"; })) verdict = "PASS_WITH_FLAGS";
    else verdict = "PASS";
    var flags = [];
    outcomes.forEach(function (o) { o.flags.forEach(function (f) { flags.push(f); }); });
    return {
      verdict: verdict, outcomes: outcomes, flags: flags,
      applied: outcomes.filter(function (o) { return o.status !== "n/a"; }).length
    };
  }

  var api = { check: check, HEDGE: HEDGE, ATTRIB: ATTRIB, EVIDENTIAL: EVIDENTIAL, sentences: sentences };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.FactwashGate = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
