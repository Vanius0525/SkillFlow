"""Character-span to token-span mapping for the whitebox stage.

Kept apart from wb_replay so it carries no numpy or torch dependency: these two
functions decide which positions every internal measurement is computed over,
which makes them the part most worth testing on a machine with no GPU.
"""

from __future__ import annotations


def char_to_token_span(offsets, lo: int, hi: int, base: int) -> tuple[int, int]:
    """Map a character span of the user message to token indices.

    ``offsets`` is the tokenizer's offset mapping over the FULL templated
    prompt; ``base`` is where the user message begins inside that prompt. A
    token counts as inside the span when it overlaps it at all, so a token
    straddling the boundary is included rather than dropped — losing the first
    token of the skill would quietly shrink every skill-span measurement.
    """
    a, b = base + lo, base + hi
    idx = [i for i, (s, e) in enumerate(offsets) if e > s and s < b and e > a]
    if not idx:
        raise ValueError(f"empty token span for chars [{lo},{hi})")
    return idx[0], idx[-1] + 1


def subsample(lo: int, hi: int, cap: int) -> list[int]:
    """Uniformly thin a span to at most ``cap`` positions.

    CKA over a few hundred positions says what it says over two thousand, and
    the cap is what keeps both conditions' span activations in memory at once
    next to an 8B model. The same indices are used for both conditions, so the
    comparison stays position-aligned.
    """
    n = hi - lo
    if n <= cap:
        return list(range(lo, hi))
    step = n / cap
    return [lo + int(i * step) for i in range(cap)]
