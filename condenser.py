#!/usr/bin/env python3
"""
Transcript condensers.

The system prompt is not what fills a context window — the transcript is. Every
tool result is resent on every subsequent call, so a handful of large ones can
exhaust a 32k window while the system prompt is still under 8k. Compressing the
system prompt buys headroom but cannot save a turn whose transcript alone
exceeds the window. A condenser bounds the transcript itself.

The interface deliberately mirrors OpenHands' Condenser so the numbers are
comparable with published work. Strategies vary on two axes:

    mechanism : heuristic (no model call) | llm (a summarisation call)
    cost      : free                      | extra inference

`HeuristicCondenser` is the free/heuristic cell. It exists to be the baseline
that any LLM-based scheme — SkillFlow's residual compression included — has to
beat before its extra inference cost is justified. Reporting a win over "no
context management at all" is not a result; reporting a win over this is.

Masking, not deletion
---------------------
Tool-use protocols require every `tool_use` block to be answered by a
`tool_result` block carrying the matching id, so dropping messages corrupts the
conversation and the provider rejects it. These condensers therefore MASK
observations in place: the action history stays intact and addressable, and only
the bulky observation text is replaced by a marker. That is what OpenHands'
`attention_window` does, and it is why masking is idempotent — a marker is
recognised and never re-masked.

Parameters (named as in OpenHands)
----------------------------------
keep_first       leading messages never masked (the task and its attachments)
attention_window most recent observation-bearing messages kept verbatim
max_size         message-count trigger; 0 means "trigger on context pressure only"
"""

import threading
from dataclasses import dataclass, field

# Recognisable prefix so a masked result is never masked twice.
ELISION_PREFIX = "[elided by condenser:"


def _elision(n_chars: int) -> str:
    return (
        f"{ELISION_PREFIX} {n_chars:,} characters of tool output were dropped to "
        f"stay inside the context window. The command that produced it is still "
        f"in the transcript above — re-run it, narrowed, if you still need the "
        f"output.]"
    )


def _as_text(content) -> str:
    """Flatten a tool_result content field (str, or list of blocks) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                parts.append(b.get("text", "") if b.get("type") == "text" else str(b))
            else:
                parts.append(str(b))
        return "\n".join(parts)
    return "" if content is None else str(content)


def _tool_result_blocks(message) -> list:
    """The tool_result blocks in a message, or [] if it carries none."""
    if not isinstance(message, dict) or message.get("role") != "user":
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [
        b for b in content
        if isinstance(b, dict) and b.get("type") == "tool_result"
    ]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@dataclass
class CondenserStats:
    """Per-task record of condenser activity."""
    name: str = "none"
    checks: int = 0
    fired: int = 0
    blocks_masked: int = 0
    chars_dropped: int = 0
    peak_messages: int = 0
    llm_calls: int = 0          # summarisation calls, 0 for the heuristic
    llm_in_tokens: int = 0
    llm_out_tokens: int = 0

    def observe(self, n_messages: int) -> None:
        self.checks += 1
        self.peak_messages = max(self.peak_messages, n_messages)


class _CondenserAggregate:
    """Process-wide condenser counters; one eval run is one process."""

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.name = "none"
        self.tasks = 0
        self.tasks_fired = 0
        self.checks = 0
        self.fired = 0
        self.blocks_masked = 0
        self.chars_dropped = 0
        self.peak_messages = 0
        self.llm_calls = 0
        self.llm_in_tokens = 0
        self.llm_out_tokens = 0

    def add(self, s: CondenserStats) -> None:
        with self._lock:
            self.name = s.name or self.name
            self.tasks += 1
            if s.fired:
                self.tasks_fired += 1
            self.checks += s.checks
            self.fired += s.fired
            self.blocks_masked += s.blocks_masked
            self.chars_dropped += s.chars_dropped
            self.peak_messages = max(self.peak_messages, s.peak_messages)
            self.llm_calls += s.llm_calls
            self.llm_in_tokens += s.llm_in_tokens
            self.llm_out_tokens += s.llm_out_tokens

    def summary(self) -> dict:
        with self._lock:
            return {
                "condenser": self.name,
                "tasks": self.tasks,
                "tasks_where_condenser_fired": self.tasks_fired,
                "checks": self.checks,
                "condensations": self.fired,
                "blocks_masked": self.blocks_masked,
                "chars_dropped": self.chars_dropped,
                "peak_messages": self.peak_messages,
                "llm_calls": self.llm_calls,
                "llm_in_tokens": self.llm_in_tokens,
                "llm_out_tokens": self.llm_out_tokens,
            }

    def render(self) -> str:
        s = self.summary()
        if s["condenser"] == "none" and not s["tasks_where_condenser_fired"]:
            return f"  condenser          : none (transcript never bounded)"
        line = (
            f"  condenser          : {s['condenser']} — fired in "
            f"{s['tasks_where_condenser_fired']}/{s['tasks']} tasks "
            f"({s['condensations']} times, {s['blocks_masked']} observations "
            f"replaced, {s['chars_dropped']:,} chars dropped)"
        )
        if s["llm_calls"]:
            line += (f"\n                       cost: {s['llm_calls']} summarisation "
                     f"calls, {s['llm_in_tokens']:,}in/{s['llm_out_tokens']:,}out")
        return line


CONDENSER_AGG = _CondenserAggregate()


# ---------------------------------------------------------------------------
# Condensers
# ---------------------------------------------------------------------------


class Condenser:
    """No-op base. Also the `--condenser none` behaviour."""

    name = "none"

    def __init__(self, stats: CondenserStats | None = None,
                 ratio: float = 0.8, **_kw):
        self.stats = stats if stats is not None else CondenserStats()
        self.stats.name = self.name
        # Own trigger ratio, deliberately separate from SkillFlow's compression
        # ratio: an ablation may well want the free heuristic to act earlier
        # than the paid summarisation.
        self.ratio = ratio

    def threshold_for(self, window: int) -> int:
        """Request size (tokens) at which this condenser starts masking."""
        return int(window * self.ratio)

    def condense(self, messages: list, prompt_tokens: int = 0,
                 threshold: int = 0, verbose: bool = False,
                 prefix: str = "") -> bool:
        """Bound `messages` in place. Returns True if anything changed."""
        self.stats.observe(len(messages))
        return False


class _MaskingCondenser(Condenser):
    """
    Shared selection policy: what gets dropped, and when.

    Subclasses differ only in `_replace`, i.e. in what stands in for a dropped
    observation. Holding the selection identical is the whole point of the
    comparison — a difference between `heuristic` and `llm` is then a
    difference in the value of summarisation, not in which events survived.

    Fires when either trigger crosses:
      * context pressure — the assembled request reaches `threshold` tokens
      * transcript size  — `max_size` messages, when max_size > 0

    Every tool_result outside `keep_first` and outside the trailing
    `attention_window` is replaced. Results already replaced, and results
    shorter than `min_mask_chars`, are left alone — so repeated pressure with
    nothing left to do is free and is not counted as a firing.
    """

    def __init__(self, stats: CondenserStats | None = None, keep_first: int = 1,
                 attention_window: int = 2, max_size: int = 0,
                 min_mask_chars: int = 200, ratio: float = 0.8, **_kw):
        super().__init__(stats, ratio=ratio)
        self.keep_first = max(0, keep_first)
        self.attention_window = max(0, attention_window)
        self.max_size = max(0, max_size)
        self.min_mask_chars = max(0, min_mask_chars)

    def _triggered(self, messages: list, prompt_tokens: int, threshold: int) -> bool:
        if threshold and prompt_tokens >= threshold:
            return True
        if self.max_size and len(messages) > self.max_size:
            return True
        return False

    def _replace(self, text: str) -> str:
        """What stands in for a dropped observation. Subclasses override."""
        raise NotImplementedError

    def condense(self, messages: list, prompt_tokens: int = 0,
                 threshold: int = 0, verbose: bool = False,
                 prefix: str = "") -> bool:
        self.stats.observe(len(messages))
        if not self._triggered(messages, prompt_tokens, threshold):
            return False

        bearing = [i for i, m in enumerate(messages) if _tool_result_blocks(m)]
        if not bearing:
            return False
        protected = set(bearing[-self.attention_window:]) if self.attention_window else set()

        masked = dropped = 0
        for i in bearing:
            if i < self.keep_first or i in protected:
                continue
            for block in _tool_result_blocks(messages[i]):
                text = _as_text(block.get("content"))
                if text.startswith(ELISION_PREFIX) or len(text) <= self.min_mask_chars:
                    continue
                block["content"] = self._replace(text)
                masked += 1
                dropped += len(text)

        if not masked:
            return False

        self.stats.fired += 1
        self.stats.blocks_masked += masked
        self.stats.chars_dropped += dropped
        if verbose:
            print(f"{prefix}[condense] {self.name}: replaced {masked} observations, "
                  f"dropped {dropped:,} chars "
                  f"(keep_first={self.keep_first}, "
                  f"attention_window={self.attention_window})", flush=True)
        return True


class HeuristicCondenser(_MaskingCondenser):
    """
    Mask old observations, keep every action. Zero model calls.

    The free/heuristic cell: whatever an LLM-based scheme buys has to be
    measured against this, not against doing nothing.
    """

    name = "heuristic"

    def _replace(self, text: str) -> str:
        return _elision(len(text))


class LLMCondenser(_MaskingCondenser):
    """
    Same selection policy, but each dropped observation is replaced by an LLM
    summary of itself rather than by a fixed marker.

    This is the paid/LLM cell, and it is the cell SkillFlow actually has to
    beat: it spends model calls on compression just as SkillFlow does, so a
    remaining gap is attributable to structure — a multi-channel residual
    against a flat per-observation summary — and not to one side simply being
    allowed to spend inference the other was not.

    `summarize` is supplied by the harness (see `make_summarizer`) so this
    module stays free of any SDK specifics and both harnesses summarise with
    byte-identical wording. Without one, it degrades to the heuristic marker
    rather than silently doing nothing.

    `max_calls_per_condensation` bounds cost: an unbounded condenser on a long
    transcript can spend more on summarising than on the task.
    """

    name = "llm"

    def __init__(self, stats: CondenserStats | None = None,
                 summarize=None, max_calls_per_condensation: int = 4, **kw):
        super().__init__(stats, **kw)
        self.summarize = summarize
        self.max_calls_per_condensation = max(1, max_calls_per_condensation)
        self._calls_this_round = 0

    def condense(self, messages: list, prompt_tokens: int = 0,
                 threshold: int = 0, verbose: bool = False,
                 prefix: str = "") -> bool:
        self._calls_this_round = 0
        return super().condense(messages, prompt_tokens, threshold, verbose, prefix)

    def _replace(self, text: str) -> str:
        if self.summarize is None or self._calls_this_round >= self.max_calls_per_condensation:
            return _elision(len(text))
        try:
            summary, in_tok, out_tok = self.summarize(text)
        except Exception as e:
            print(f"  [WARN] condenser summarisation failed ({type(e).__name__}: {e});"
                  f" falling back to elision", flush=True)
            return _elision(len(text))
        self._calls_this_round += 1
        self.stats.llm_calls += 1
        self.stats.llm_in_tokens += in_tok
        self.stats.llm_out_tokens += out_tok
        if not summary.strip():
            return _elision(len(text))
        return (f"{ELISION_PREFIX} {len(text):,} characters of tool output were "
                f"summarised to stay inside the context window. Summary follows; "
                f"re-run the command above, narrowed, if you need the raw output.]"
                f"\n{summary.strip()}")


# ---------------------------------------------------------------------------
# Summariser shared by both harnesses
# ---------------------------------------------------------------------------

SUMMARY_SYSTEM = """\
You compress one piece of tool output so an agent can keep working without the \
full text. Preserve every concrete value the agent might still need: numbers, \
names, dates, file paths, URLs, identifiers, column headers, and any error \
message verbatim. Drop formatting, boilerplate and repetition. Never invent a \
value that is not in the input. Output the summary only, with no preamble."""


def make_summarizer(client, model: str, task_hint: str = "", max_tokens: int = 256):
    """
    Build the `summarize` callable for LLMCondenser.

    `task_hint` (the question, or SkillFlow's goal objective) is passed so the
    summary can keep what this task needs. Both harnesses supply it, so the
    only thing that differs between them is the task, not the prompt.
    """
    hint = (task_hint or "").strip()

    def summarize(text: str):
        prompt = (
            (f"## Task the agent is working on\n{hint[:600]}\n\n" if hint else "")
            + f"## Tool output to compress\n{text}\n\nWrite the summary now."
        )
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=SUMMARY_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        summary = "".join(
            b.text for b in resp.content if getattr(b, "text", None)
        ).strip()
        return summary, resp.usage.input_tokens, resp.usage.output_tokens

    return summarize


CONDENSERS = {
    "none": Condenser,
    "heuristic": HeuristicCondenser,
    "llm": LLMCondenser,
}


def make_condenser(name: str = "none", stats: CondenserStats | None = None,
                   **kwargs) -> Condenser:
    """Build a condenser by name. Unknown names raise rather than silently no-op."""
    try:
        cls = CONDENSERS[name]
    except KeyError:
        raise ValueError(
            f"unknown condenser {name!r}; available: {', '.join(CONDENSERS)}"
        ) from None
    return cls(stats=stats, **kwargs)


def add_condenser_args(parser) -> None:
    """Register the shared condenser CLI flags on an argparse parser."""
    parser.add_argument(
        "--condenser", choices=sorted(CONDENSERS), default="none",
        help="transcript condenser (default: none). 'heuristic' masks old tool "
             "observations with no extra model call — the OpenHands-style "
             "baseline any LLM-based context management should be measured "
             "against. 'llm' replaces them with a summary instead, at the cost "
             "of one model call each — same selection policy, paid mechanism.")
    parser.add_argument(
        "--condenser-max-calls", type=int, default=4,
        help="for --condenser llm: max summarisation calls per condensation "
             "(default: 4). Bounds what compression may cost per firing.")
    parser.add_argument(
        "--keep-first", type=int, default=1,
        help="leading messages the condenser never masks (default: 1)")
    parser.add_argument(
        "--attention-window", type=int, default=2,
        help="most recent observation-bearing messages kept verbatim (default: 2)")
    parser.add_argument(
        "--condenser-max-size", type=int, default=0,
        help="message-count trigger; 0 = trigger on context pressure only")
    parser.add_argument(
        "--condense-ratio", type=float, default=0.8,
        help="fraction of the context window at which the condenser starts "
             "masking (default: 0.8). Separate from --compress-ratio so the "
             "free heuristic and the paid summarisation can be tuned apart.")


def condenser_from_args(args, stats: CondenserStats | None = None) -> Condenser:
    """Build the condenser described by parsed CLI args."""
    return make_condenser(
        getattr(args, "condenser", "none"),
        stats=stats,
        keep_first=getattr(args, "keep_first", 1),
        attention_window=getattr(args, "attention_window", 2),
        max_size=getattr(args, "condenser_max_size", 0),
        ratio=getattr(args, "condense_ratio", 0.8),
        max_calls_per_condensation=getattr(args, "condenser_max_calls", 4),
    )
