"""Limits that keep one request, or one busy afternoon, from turning into an unbounded model bill.

Every limit is read from the environment with a default that fits normal use, so an operator can
tighten them on a shared server without a code change. A request that breaks a limit gets a
normal declined response (needs_human=true with the reason), never an exception: the UI and any
agent calling the API already know how to show a decline.

    input     MAX_DOCUMENT_CHARS, MAX_FIELD_CHARS, MAX_QUESTION_CHARS
    output    LLM_MAX_TOKENS, LLM_TIMEOUT (applied in llm.py)
    volume    MAX_CALLS_PER_MINUTE, MAX_CALLS_PER_DAY, LLM_CONCURRENCY (shared by both endpoints)
"""

import os
import threading
import time
from collections import deque


def _int(name: str, default: int) -> int:
    return int(os.getenv(name) or default)


# A long open-access paper is 40,000-60,000 characters; 80,000 (about 20,000 tokens) keeps every real
# paper whole and stops a pasted book or log file.
MAX_DOCUMENT_CHARS = _int("MAX_DOCUMENT_CHARS", 80_000)
MAX_FIELD_CHARS = _int("MAX_FIELD_CHARS", 500)  # title, source, focus
MAX_QUESTION_CHARS = _int("MAX_QUESTION_CHARS", 2_000)
# A card is about 600-1,200 output tokens in two languages; 2,000 leaves room and stops a runaway reply.
LLM_MAX_TOKENS = _int("LLM_MAX_TOKENS", 2_000)
LLM_TIMEOUT = _int("LLM_TIMEOUT", 120)
# Model calls that may run at once across both endpoints; the rest wait in Gradio's queue.
LLM_CONCURRENCY = _int("LLM_CONCURRENCY", 2)
MAX_CALLS_PER_MINUTE = _int("MAX_CALLS_PER_MINUTE", 20)
MAX_CALLS_PER_DAY = _int("MAX_CALLS_PER_DAY", 500)


def check_lengths(fields: dict[str, tuple[str | None, int]]) -> str | None:
    """The reason the first over-long field is refused, or None when all fit. fields: name -> (value, limit)."""
    for name, (value, limit) in fields.items():
        if value and len(value) > limit:
            return f"{name} is {len(value):,} characters; the limit is {limit:,}"
    return None


class CallBudget:
    """A sliding one-minute window and a rolling 24-hour count of model calls, for the whole server.

    Global, not per user: the app has no login of its own (identity comes from the proxy in front of
    it), and the cost to protect is the shared model bill. In memory, so a restart resets it, which
    is acceptable for a cost brake on a single container.
    """

    def __init__(self, *, per_minute: int, per_day: int, clock=time.monotonic):
        self.per_minute, self.per_day, self.clock = per_minute, per_day, clock
        self.calls: deque[float] = deque()
        self.lock = threading.Lock()

    def take(self) -> str | None:
        """Record one call and return None, or return why it is refused without recording it."""
        with self.lock:
            now = self.clock()
            while self.calls and now - self.calls[0] > 86_400:
                self.calls.popleft()
            if len(self.calls) >= self.per_day:
                return f"the daily limit of {self.per_day} model calls is reached; try again later"
            if sum(1 for t in self.calls if now - t <= 60) >= self.per_minute:
                return f"more than {self.per_minute} requests in the last minute; wait a moment and retry"
            self.calls.append(now)
            return None


BUDGET = CallBudget(per_minute=MAX_CALLS_PER_MINUTE, per_day=MAX_CALLS_PER_DAY)
