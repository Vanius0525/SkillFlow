"""Per-layer, per-span representation metrics for the whitebox stage.

All of these take a single span's hidden states, ``Z`` of shape (n_tokens, d),
for one layer, and return a scalar. They are pure functions of a numpy array so
they can be checked without a GPU; the model-side code lives in wb_replay.py.

Three come from Layer by Layer (arXiv 2502.02013, ICML'25), which showed that
intermediate layers carry the better representations and that autoregressive
decoders have a mid-depth compression valley — the region where a skill would
have to act if it acts on the representation at all:

  prompt_entropy   matrix-based entropy of the token embeddings in one span.
                   High = features spread across many directions, low =
                   compressed. Computed from the Gram matrix eigenvalues, so it
                   needs no density estimate and no training.
  curvature        mean angle between consecutive token difference vectors.
                   High = the trajectory through embedding space turns sharply
                   (local features), low = smooth (global structure).
  effective_rank   exp(S_1(Z)); how many directions the span actually uses.

The fourth comes from the uncertainty paper (arXiv 2604.05306), whose CKA
analysis separated two things that look identical in parameter space:
sharpening a structure the pretrained model already has (CKA stays near 1.0 at
every layer) from building a new internal state (CKA falls in late layers).
That distinction is the representational form of our H1-vs-H2 question, which
is why it is the one measurement here that compares two runs rather than
describing one:

  linear_cka       similarity of two representations of the SAME positions
                   under the two conditions. Invariant to rotation and to
                   isotropic scaling, not to arbitrary per-feature scaling.

Numerical notes that matter more than they look:
  * Everything is done in float64. bf16 hidden states have ~3 decimal digits;
    eigenvalues of a Gram matrix built from them are noise below ~1e-3.
  * Entropy is computed from eigenvalues of the normalised Gram matrix, whose
    trace is 1 by construction, so the scale of the activations drops out.
    Without that, a layer with larger residual norms would look "higher
    entropy" purely because of norm growth across depth.
"""

from __future__ import annotations

import numpy as np

EPS = 1e-12


def _gram(Z: np.ndarray) -> np.ndarray:
    """Normalised Gram matrix K/tr(K) — trace one, so activation scale drops out."""
    Z = np.asarray(Z, dtype=np.float64)
    if Z.ndim != 2:
        raise ValueError(f"expected (n_tokens, d), got {Z.shape}")
    K = Z @ Z.T
    tr = float(np.trace(K))
    if tr <= EPS:
        return np.zeros_like(K)
    return K / tr


def eigenvalues(Z: np.ndarray) -> np.ndarray:
    K = _gram(Z)
    if K.size == 0:
        return np.zeros(0)
    w = np.linalg.eigvalsh(K)
    return np.clip(w, 0.0, None)


def prompt_entropy(Z: np.ndarray, alpha: float = 1.0) -> float:
    """Matrix-based entropy S_alpha of one span's token embeddings.

    alpha -> 1 is the von Neumann limit, -sum p log p over the normalised
    eigenvalues, which is what Layer by Layer uses by default.
    """
    w = eigenvalues(Z)
    w = w[w > EPS]
    if w.size == 0:
        return 0.0
    if abs(alpha - 1.0) < 1e-9:
        return float(-np.sum(w * np.log(w)))
    return float(np.log(np.sum(w ** alpha)) / (1.0 - alpha))


def effective_rank(Z: np.ndarray) -> float:
    """exp(S_1(Z)) — the number of directions the span effectively occupies."""
    return float(np.exp(prompt_entropy(Z, alpha=1.0)))


def curvature(Z: np.ndarray) -> float:
    """Mean angle between consecutive token difference vectors.

    Needs at least three tokens: two difference vectors. Returns nan for spans
    shorter than that rather than a made-up zero, so short spans are visibly
    excluded instead of silently dragging an average down.
    """
    Z = np.asarray(Z, dtype=np.float64)
    if Z.shape[0] < 3:
        return float("nan")
    V = np.diff(Z, axis=0)
    n = np.linalg.norm(V, axis=1)
    ok = (n[:-1] > EPS) & (n[1:] > EPS)
    if not np.any(ok):
        return float("nan")
    cos = np.sum(V[:-1] * V[1:], axis=1) / (n[:-1] * n[1:])
    return float(np.mean(np.arccos(np.clip(cos[ok], -1.0, 1.0))))


def linear_cka(X: np.ndarray, Y: np.ndarray) -> float:
    """Linear CKA between two representations of the same positions.

    X and Y must have the same number of rows, each row the same token under
    the two conditions. Both are column-centred first: without centring this
    is dominated by the mean activation, which is large and nearly identical
    in the two runs, and every layer would report ~1.0.
    """
    X = np.asarray(X, dtype=np.float64)
    Y = np.asarray(Y, dtype=np.float64)
    if X.shape[0] != Y.shape[0]:
        raise ValueError(f"row mismatch: {X.shape[0]} vs {Y.shape[0]}")
    if X.shape[0] < 2:
        return float("nan")
    X = X - X.mean(axis=0, keepdims=True)
    Y = Y - Y.mean(axis=0, keepdims=True)
    hsic = float(np.linalg.norm(X.T @ Y, ord="fro") ** 2)
    nx = float(np.linalg.norm(X.T @ X, ord="fro"))
    ny = float(np.linalg.norm(Y.T @ Y, ord="fro"))
    if nx <= EPS or ny <= EPS:
        return float("nan")
    return hsic / (nx * ny)


def span_profile(Z: np.ndarray) -> dict:
    """All single-run scalars for one span at one layer."""
    return {
        "n_tokens": int(np.asarray(Z).shape[0]),
        "entropy": prompt_entropy(Z),
        "eff_rank": effective_rank(Z),
        "curvature": curvature(Z),
    }


def kl_divergence(p_logits: np.ndarray, q_logits: np.ndarray) -> float:
    """KL(p || q) between two next-token distributions given as logits.

    Used for the position-level localisation readout (M3): which positions
    absorb the distributional change when the skill is present.
    """
    p = np.asarray(p_logits, dtype=np.float64)
    q = np.asarray(q_logits, dtype=np.float64)
    p = p - p.max()
    q = q - q.max()
    lp = p - np.log(np.sum(np.exp(p)))
    lq = q - np.log(np.sum(np.exp(q)))
    return float(np.sum(np.exp(lp) * (lp - lq)))
