from __future__ import annotations

import time
from collections import deque


class TokenRateLimiter:
    """Conservative rolling-window limiter for estimated input plus output tokens."""

    def __init__(self, tokens_per_minute: int) -> None:
        if tokens_per_minute <= 0:
            raise ValueError("tokens_per_minute must be greater than zero")
        self.tokens_per_minute = tokens_per_minute
        self.entries: deque[tuple[float, int]] = deque()

    def reserve(self, tokens: int) -> None:
        if tokens > self.tokens_per_minute:
            raise ValueError("One request exceeds MISTRAL_TPM; reduce MISTRAL_CONTEXT_CHARS or output reserve.")
        while True:
            now = time.monotonic()
            while self.entries and now - self.entries[0][0] >= 60:
                self.entries.popleft()
            used = sum(entry_tokens for _, entry_tokens in self.entries)
            if used + tokens <= self.tokens_per_minute:
                self.entries.append((now, tokens))
                return
            wait_seconds = max(0.05, 60 - (now - self.entries[0][0]))
            time.sleep(min(wait_seconds, 55))
