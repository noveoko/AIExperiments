"""
End-to-End Regex Evolution Pipeline for Person Name Extraction
Uses ShinkaEvolve-style evolutionary algorithm (genetic programming)

Pipeline Overview:
  1. Ingest → Parse inputs (doc, names, non-names)
  2. Fitness → Score each regex candidate
  3. Evolve  → Mutate / crossover population
  4. Select  → Keep best candidates (elitism + tournament)
  5. Output  → Best regex (≤ 250 chars)
"""

import re
import random
import string
import json
import time
from dataclasses import dataclass, field
from typing import Optional
from copy import deepcopy

# ─────────────────────────────────────────────
# 1.  DATA MODEL
# ─────────────────────────────────────────────

@dataclass
class Individual:
    """One candidate regex pattern in the population."""
    pattern: str
    fitness: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    generation: int = 0

    def __len__(self):
        return len(self.pattern)


@dataclass
class EvolutionConfig:
    """Hyperparameters for the evolutionary run."""
    population_size: int = 60
    max_generations: int = 100
    max_pattern_len: int = 250          # hard constraint
    elite_fraction: float = 0.15        # top N% always survive
    tournament_size: int = 5
    crossover_rate: float = 0.6
    mutation_rate: float = 0.4
    target_f1: float = 0.98             # stop early if hit
    seed: int = 42


# ─────────────────────────────────────────────
# 2.  CORPUS INGESTION
# ─────────────────────────────────────────────

class CorpusParser:
    """
    Accepts:
        doc        – raw natural-language text (any size)
        names      – list[str] of known person names IN the doc
        non_names  – list[str] of words/phrases that are NOT names

    Produces positive / negative test cases for fitness evaluation.
    """

    def __init__(self, doc: str, names: list[str], non_names: list[str]):
        self.doc = doc
        self.names = [n.strip() for n in names if n.strip()]
        self.non_names = [w.strip() for w in non_names if w.strip()]
        self.positives, self.negatives = self._build_test_cases()

    def _build_test_cases(self):
        """
        Positives: every name that actually appears in the document.
        Negatives: non_names that appear in the document + common words.
        """
        positives = []
        for name in self.names:
            # Find all occurrences with surrounding context
            for m in re.finditer(re.escape(name), self.doc):
                start = max(0, m.start() - 30)
                end   = min(len(self.doc), m.end() + 30)
                positives.append({
                    "context": self.doc[start:end],
                    "target":  name
                })

        negatives = []
        for word in self.non_names:
            for m in re.finditer(re.escape(word), self.doc):
                start = max(0, m.start() - 30)
                end   = min(len(self.doc), m.end() + 30)
                negatives.append({
                    "context": self.doc[start:end],
                    "target":  word
                })

        return positives, negatives

    def summary(self):
        return (f"Corpus: {len(self.doc):,} chars | "
                f"{len(self.positives)} positive cases | "
                f"{len(self.negatives)} negative cases")


# ─────────────────────────────────────────────
# 3.  FITNESS FUNCTION
# ─────────────────────────────────────────────

class FitnessEvaluator:
    """
    Scores a regex on:
      • Precision  = TP / (TP + FP)
      • Recall     = TP / (TP + FN)
      • F1         = harmonic mean of P and R
      • Length penalty: patterns > 200 chars are penalised
    """

    def __init__(self, corpus: CorpusParser, config: EvolutionConfig):
        self.corpus = corpus
        self.config = config

    def evaluate(self, individual: Individual) -> Individual:
        try:
            compiled = re.compile(individual.pattern, re.IGNORECASE)
        except re.error:
            individual.fitness = 0.0
            return individual

        tp = fp = fn = 0

        # True Positives + False Negatives
        for case in self.corpus.positives:
            matches = compiled.findall(case["context"])
            # Check if target is among the matches
            hit = any(
                case["target"].lower() in m.lower()
                if isinstance(m, str) else
                case["target"].lower() in " ".join(m).lower()
                for m in matches
            )
            if hit:
                tp += 1
            else:
                fn += 1

        # False Positives
        for case in self.corpus.negatives:
            matches = compiled.findall(case["context"])
            hit = any(
                case["target"].lower() in m.lower()
                if isinstance(m, str) else
                case["target"].lower() in " ".join(m).lower()
                for m in matches
            )
            if hit:
                fp += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1        = (2 * precision * recall / (precision + recall)
                     if (precision + recall) > 0 else 0.0)

        # Length penalty: smooth penalty starts at 200 chars
        length_penalty = 1.0
        if len(individual.pattern) > 200:
            excess = len(individual.pattern) - 200
            length_penalty = max(0.5, 1.0 - excess * 0.005)

        individual.precision = precision
        individual.recall    = recall
        individual.f1        = f1
        individual.fitness   = f1 * length_penalty
        return individual


# ─────────────────────────────────────────────
# 4a.  REGEX SYMBOL COMPOSER
#      Generates random valid regex fragments from
#      first-principles — no curated atom lists.
#      Every legal regex construct is reachable.
# ─────────────────────────────────────────────

class RegexSymbolComposer:
    """
    Builds regex fragments by randomly composing from the complete
    set of regex metacharacters and syntax rules.

    This is fundamentally different from a static atom list:
    instead of choosing from pre-written strings, it constructs
    novel expressions by walking a probabilistic grammar tree.

    The grammar (BNF-style):
    ─────────────────────────────────────────────
    pattern       ::= anchor? expr+ anchor?
    expr          ::= term quantifier?
    term          ::= char_class
                    | shorthand
                    | literal_char
                    | dot
                    | group
                    | lookaround
                    | alternation_expr
    char_class    ::= '[' negation? class_item+ ']'
    class_item    ::= range_item | shorthand | literal_char | posix_class
    range_item    ::= char '-' char          (e.g. A-Z, a-z, 0-9, \u0100-\u017E)
    group         ::= non_capture_group | capture_group
    non_capture_group ::= '(?:' expr+ ')' quantifier?
    lookaround    ::= lookbehind | lookahead
    lookbehind    ::= '(?<=' simple_expr ')' | '(?<!' simple_expr ')'
    lookahead     ::= '(?='  simple_expr ')' | '(?!'  simple_expr ')'
    alternation_expr  ::= '(?:' branch '|' branch ('|' branch)* ')'
    branch        ::= expr+
    quantifier    ::= '*' | '+' | '?' | '{n}' | '{n,m}' | '{n,}'
                    (any may be made lazy with trailing '?')
    anchor        ::= '\\b' | '\\B' | '^' | '$' | lookbehind | lookahead
    shorthand     ::= '\\w' | '\\W' | '\\s' | '\\S' | '\\d' | '\\D'
    ─────────────────────────────────────────────

    Key design decisions:
      • Unicode ranges are sampled randomly (not hard-coded) so the
        composer can discover e.g. Cyrillic, Greek, or Latin Extended
        ranges by chance — and keep them if they improve fitness.
      • Alternation branches are assembled from other random terms
        so e.g. (?:Mr|Dr|Prof|Sir) might emerge spontaneously.
      • Lookarounds are generated with simple sub-expressions to avoid
        catastrophic backtracking.
      • All outputs are validated; invalid patterns fall back to a
        safe seeded template.
    """

    # ── Raw symbol tables (minimal, primitives only) ──────────

    # Every regex metacharacter / special sequence
    META = list(r". * + ? ^ $ { } [ ] \ | ( )")

    SHORTHAND_CLASSES = [r"\w", r"\W", r"\s", r"\S", r"\d", r"\D"]

    # Printable ASCII chars useful in name patterns (unescaped)
    NAME_CHARS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'-.,")

    # Unicode code-point ranges relevant to human names
    # Stored as (start_cp, end_cp, description)
    UNICODE_BLOCKS = [
        (0x00C0, 0x00D6, "Latin upper accented"),   # À–Ö
        (0x00D8, 0x00F6, "Latin lower accented"),   # Ø–ö
        (0x00F8, 0x00FF, "Latin extended lower"),   # ø–ÿ
        (0x0100, 0x017E, "Latin Extended-A"),        # Ā–ž
        (0x0180, 0x024F, "Latin Extended-B"),        # ƀ–ɏ
        (0x0400, 0x04FF, "Cyrillic"),
        (0x0370, 0x03FF, "Greek"),
        (0x0600, 0x06FF, "Arabic"),
        (0x4E00, 0x9FFF, "CJK Unified"),
        (0xAC00, 0xD7AF, "Hangul"),
        (0x0900, 0x097F, "Devanagari"),
    ]

    QUANTIFIERS_RAW = ["", "?", "+", "*", "{1,2}", "{1,3}", "{2,4}",
                       "{0,2}", "{1,}", "{2,}", "{2}", "{3}"]

    ANCHORS_RAW = [r"\b", r"\B", r"(?<!\w)", r"(?<=\s)", r"(?=\s)",
                   r"(?!\w)", r"(?<=^)", r"(?=\W|$)"]

    def __init__(self, rng: random.Random):
        self.rng = rng           # shared RNG instance for reproducibility

    # ────────────────────────────────────────────
    # Low-level primitives
    # ────────────────────────────────────────────

    def _random_unicode_range(self) -> str:
        """
        Returns a random Unicode range string for use inside a char class.

        Strategy:
          60% — pick one of the predefined blocks (most useful for names)
          25% — random adjacent range within a block (e.g. \\u0041-\\u005A)
          15% — fully random range (may be exotic / useless, filtered by fitness)
        """
        r = self.rng.random()
        if r < 0.60:
            start, end, _ = self.rng.choice(self.UNICODE_BLOCKS)
            # Pick a sub-range within the block (keeps patterns shorter)
            sub_start = self.rng.randint(start, max(start, end - 10))
            sub_end   = min(end, sub_start + self.rng.randint(5, 80))
            return rf"\u{sub_start:04X}-\u{sub_end:04X}"
        elif r < 0.85:
            # Random adjacent range — might find e.g. A-Z by luck
            base = self.rng.randint(0x0041, 0x024F)
            span = self.rng.randint(3, 30)
            return rf"\u{base:04X}-\u{min(base+span, 0xFFFF):04X}"
        else:
            # Fully random (rarely useful, kept for exploration)
            lo = self.rng.randint(0x0020, 0xD7FF)
            hi = min(lo + self.rng.randint(1, 100), 0xD7FF)
            return rf"\u{lo:04X}-\u{hi:04X}"

    def _random_ascii_range(self) -> str:
        """
        Returns a random ASCII range like A-Z, a-z, A-Za-z, etc.

        Strategy:
          40% — common letter ranges
          30% — digit or mixed
          30% — random printable ASCII range
        """
        r = self.rng.random()
        if r < 0.40:
            return self.rng.choice(["A-Z", "a-z", "A-Za-z", "a-zA-Z"])
        elif r < 0.70:
            return self.rng.choice(["0-9", "A-Z0-9", "a-z0-9"])
        else:
            # Random printable ASCII range (0x20–0x7E)
            lo = self.rng.randint(0x41, 0x7A)
            hi = min(lo + self.rng.randint(3, 25), 0x7E)
            lo_c = chr(lo)
            hi_c = chr(hi)
            if lo_c.isalnum() and hi_c.isalnum():
                return f"{lo_c}-{hi_c}"
            return "A-Za-z"   # safe fallback

    def _random_class_item(self) -> str:
        """One item inside a [...] character class."""
        choice = self.rng.randint(0, 4)
        if choice == 0:
            return self._random_ascii_range()
        elif choice == 1:
            return self._random_unicode_range()
        elif choice == 2:
            return self.rng.choice(self.SHORTHAND_CLASSES)
        elif choice == 3:
            c = self.rng.choice(self.NAME_CHARS)
            # Escape chars that are special inside []
            return re.escape(c) if c in r"\.^$|?*+{}()[]" else c
        else:
            # Literal hyphen or apostrophe (useful for names)
            return self.rng.choice([r"\-", r"'", r"\."])

    def _build_char_class(self) -> str:
        """
        Constructs a character class [...]  by assembling 1–4 items.

        Examples of what can be produced:
            [A-Z]
            [a-zA-Z\u00C0-\u00D6]
            [^\s\d]
            [A-Za-z'-]
            [\w\u0400-\u04FF]
        """
        n_items = self.rng.randint(1, 4)
        items = [self._random_class_item() for _ in range(n_items)]
        # 5% chance of negation
        prefix = "^" if self.rng.random() < 0.05 else ""
        return "[" + prefix + "".join(items) + "]"

    def _random_quantifier(self, lazy_prob: float = 0.15) -> str:
        q = self.rng.choice(self.QUANTIFIERS_RAW)
        # Make lazy occasionally (avoids catastrophic backtracking)
        if q in ("+", "*") and self.rng.random() < lazy_prob:
            q += "?"
        return q

    def _random_anchor(self) -> str:
        return self.rng.choice(self.ANCHORS_RAW)

    # ────────────────────────────────────────────
    # Mid-level: terms and groups
    # ────────────────────────────────────────────

    def _random_literal(self) -> str:
        """A single escaped literal char useful near names."""
        c = self.rng.choice(self.NAME_CHARS)
        return re.escape(c) if c in r"\.^$|?*+{}()[]" else c

    def _simple_expr(self, depth: int = 0) -> str:
        """
        A simplified expression (used inside lookarounds to prevent
        catastrophic backtracking — no nested lookarounds allowed).
        """
        choice = self.rng.randint(0, 3)
        if choice == 0:
            return self._build_char_class() + self._random_quantifier()
        elif choice == 1:
            return self.rng.choice(self.SHORTHAND_CLASSES) + self._random_quantifier()
        elif choice == 2:
            return self._random_literal()
        else:
            return self.rng.choice(["A-Z", r"\w", r"\s"])   # safe fallback

    def _random_lookaround(self) -> str:
        """
        Generates a lookahead or lookbehind assertion.

        Types:
            (?=...)   positive lookahead
            (?!...)   negative lookahead
            (?<=...)  positive lookbehind  (fixed-width only)
            (?<!...)  negative lookbehind  (fixed-width only)

        Lookbehinds must match a fixed-width expression in Python,
        so we use simple single-char or fixed literals there.
        """
        kind = self.rng.choice(["ahead_pos", "ahead_neg", "behind_pos", "behind_neg"])

        if kind == "ahead_pos":
            return f"(?={self._simple_expr()})"
        elif kind == "ahead_neg":
            return f"(?!{self._simple_expr()})"
        elif kind == "behind_pos":
            # Fixed-width: use a single shorthand or literal
            inner = self.rng.choice([r"\s", r"\w", r"\W", " ", r"\."])
            return f"(?<={inner})"
        else:
            inner = self.rng.choice([r"\s", r"\w", r"\W", " ", r"\."])
            return f"(?<!{inner})"

    def _random_alternation(self, depth: int = 0) -> str:
        """
        Generates (?:branch1|branch2|...) where each branch
        is 1–3 simple terms.

        This can produce things like:
            (?:Mr|Dr|Prof|Sir)
            (?:[A-Z][a-z]+|[A-Z]{2,4})
            (?:\s+|\-)
        """
        n_branches = self.rng.randint(2, 4)
        branches = []
        for _ in range(n_branches):
            n_terms = self.rng.randint(1, 3)
            branch = "".join(self._random_term(depth + 1) for _ in range(n_terms))
            branches.append(branch)
        return "(?:" + "|".join(branches) + ")"

    def _random_group(self, depth: int = 0) -> str:
        """
        Generates a grouped sub-expression with a quantifier.

        Types:
            (?:...)    non-capturing (most common, no overhead)
            (...)      capturing group (useful if caller uses groups)

        The group contains 1–3 inner terms and optionally a quantifier.
        """
        n_inner = self.rng.randint(1, 3)
        inner = "".join(self._random_term(depth + 1) for _ in range(n_inner))
        if self.rng.random() < 0.8:
            wrapper = f"(?:{inner})"
        else:
            wrapper = f"({inner})"
        return wrapper + self._random_quantifier()

    def _random_term(self, depth: int = 0) -> str:
        """
        One complete regex term (the core recursive unit).

        At depth 0 (top level), all constructs are available.
        At depth ≥ 2, groups and lookarounds are suppressed to
        prevent runaway recursion and over-long patterns.

        Probability weights (depth 0):
            40%  char class  + quantifier
            15%  shorthand   + quantifier
            10%  literal
            10%  lookaround  (zero-width, powerful)
            15%  group       (recursive, high expressiveness)
            10%  alternation (discovers title sets, etc.)
        """
        if depth >= 2:
            # Simple terms only at deep nesting
            choice = self.rng.randint(0, 2)
        else:
            choice = self.rng.choices(
                range(6), weights=[40, 15, 10, 10, 15, 10])[0]

        if choice == 0:
            return self._build_char_class() + self._random_quantifier()
        elif choice == 1:
            return self.rng.choice(self.SHORTHAND_CLASSES) + self._random_quantifier()
        elif choice == 2:
            return self._random_literal()
        elif choice == 3:
            return self._random_lookaround()
        elif choice == 4:
            return self._random_group(depth)
        else:
            return self._random_alternation(depth)

    # ────────────────────────────────────────────
    # Top-level: full pattern generation
    # ────────────────────────────────────────────

    def compose(self, max_len: int = 250) -> str:
        """
        Compose a complete regex pattern from scratch.

        Structure:  [anchor] term{1,6} [anchor]

        Every call produces a structurally different pattern.
        Invalid patterns (rare, from e.g. unbalanced brackets after
        crossover) return a validated fallback.

        Returns
        -------
        str — a valid Python regex pattern, ≤ max_len chars
        """
        parts = []

        # Optional opening anchor (45% chance)
        if self.rng.random() < 0.45:
            parts.append(self._random_anchor())

        # 1–6 terms
        n_terms = self.rng.choices(range(1, 7), weights=[5, 20, 30, 25, 15, 5])[0]
        for _ in range(n_terms):
            parts.append(self._random_term(depth=0))

        # Optional closing anchor (45% chance)
        if self.rng.random() < 0.45:
            parts.append(self.rng.choice([r"\b", r"(?!\w)", r"(?=[\s,\.]|$)"]))

        pattern = "".join(parts)[:max_len]

        try:
            re.compile(pattern)
            return pattern
        except re.error:
            # Fallback to a known-valid seed template
            return self.rng.choice(RegexGenePool.SEED_TEMPLATES)


# ─────────────────────────────────────────────
# 4b.  REGEX GENE POOL
#      Wraps RegexSymbolComposer and provides the
#      interface the rest of the pipeline uses.
# ─────────────────────────────────────────────

class RegexGenePool:
    """
    Generates regex fragments by combining primitive regex symbols.

    Instead of a fixed list of hand-crafted atoms, this class defines
    the complete alphabet of regex primitives and rules for assembling
    them into valid fragments. The evolutionary algorithm can then
    discover patterns a human would never think