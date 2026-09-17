from __future__ import annotations

import json
import os
import re
import time

from groq import Groq

from .models import Plan
from .rate_limit import TokenRateLimiter

_THINK_BLOCK = re.compile(r"<think>.*?</think>\s*", flags=re.DOTALL | re.IGNORECASE)


class GroqAgent:
    """Groq Qwen client with conservative RPM/TPM pacing and 429 backoff."""

    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
        self.client = Groq(api_key=api_key)
        self.model = model or os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        rpm = float(os.getenv("GROQ_RPM", "12"))
        tpm = int(os.getenv("GROQ_TPM", "8000"))
        safety_ratio = float(os.getenv("GROQ_TPM_SAFETY_RATIO", "0.70"))
        if rpm <= 0 or tpm <= 0 or not 0 < safety_ratio <= 1:
            raise ValueError("GROQ_RPM/TPM must be positive and safety ratio must be in (0, 1].")
        self.min_interval_seconds = 60 / rpm
        self.max_retries = int(os.getenv("GROQ_MAX_RETRIES", "4"))
        self.next_request_at = 0.0
        self.plan_output_tokens = int(os.getenv("GROQ_PLAN_MAX_TOKENS", "500"))
        self.patch_output_tokens = int(os.getenv("GROQ_PATCH_MAX_TOKENS", "1000"))
        self.plan_reasoning = os.getenv("GROQ_PLAN_REASONING_EFFORT", "none")
        self.patch_reasoning = os.getenv("GROQ_PATCH_REASONING_EFFORT", "low")
        self.token_limiter = TokenRateLimiter(int(tpm * safety_ratio))

    @staticmethod
    def _estimate_tokens(messages: list[dict[str, str]], output_tokens: int) -> int:
        return max(1, (sum(len(message.get("content", "")) for message in messages) + 3) // 4 + output_tokens)

    @staticmethod
    def _final_content(content: str | None) -> str:
        """Defend against raw Qwen <think> output if a provider ignores parsed reasoning."""
        return _THINK_BLOCK.sub("", content or "").strip()

    def _complete(self, *, messages: list[dict[str, str]], max_tokens: int, reasoning_effort: str, response_format: dict[str, str] | None = None) -> str:
        estimated_tokens = self._estimate_tokens(messages, max_tokens)
        for attempt in range(self.max_retries + 1):
            self.token_limiter.reserve(estimated_tokens)
            wait = self.next_request_at - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.next_request_at = time.monotonic() + self.min_interval_seconds
            try:
                options: dict[str, object] = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0,
                    "max_completion_tokens": max_tokens,
                    "reasoning_effort": reasoning_effort,
                    # Parsed reasoning keeps <think> content out of JSON and diffs.
                    "reasoning_format": "parsed",
                }
                if response_format:
                    options["response_format"] = response_format
                response = self.client.chat.completions.create(**options)
                return self._final_content(response.choices[0].message.content)
            except Exception as error:
                status_code = getattr(error, "status_code", None)
                limited = status_code == 429 or "429" in str(error)
                if not limited or attempt == self.max_retries:
                    raise
                retry_after = getattr(getattr(error, "response", None), "headers", {}).get("retry-after")
                try:
                    delay = float(retry_after) if retry_after else 2 ** attempt
                except (TypeError, ValueError):
                    delay = 2 ** attempt
                self.next_request_at = max(self.next_request_at, time.monotonic() + max(self.min_interval_seconds, delay))
        raise RuntimeError("Unreachable retry state")

    def plan(self, context: str, test_command: str) -> Plan:
        prompt = f'''You are a cautious software engineering planner. Return only a JSON object matching this schema: {{"summary":str,"in_scope":bool,"scope_reason":str,"steps":[{{"id":str,"description":str,"target_files":[str],"acceptance_criteria":[str]}}],"test_command":str}}. Reject vague or broad tasks by setting in_scope false. Make a small, testable plan. Respect existing repository structure and test conventions. Default test command: {test_command}\n\n{context}'''
        content = self._complete(messages=[{"role": "user", "content": prompt}], max_tokens=self.plan_output_tokens, reasoning_effort=self.plan_reasoning, response_format={"type": "json_object"})
        return Plan.model_validate(json.loads(content))

    def patch(self, context: str, plan: Plan, feedback: str = "") -> str:
        prompt = f"""You are a coding agent. Produce ONLY an applicable Git unified diff: no prose, no explanation, no Markdown code fences. Your entire response must start with `diff --git` and contain nothing else.
Implement this plan: {plan.model_dump_json()}
The existing tests in context are the acceptance oracle. Do not modify test files when they already cover this behavior; patch the production source only.
For every modified existing file, begin with exactly `diff --git a/PATH b/PATH`, followed by `--- a/PATH` and `+++ b/PATH`. Include exact unchanged context from the supplied source. Do not represent an existing file as a new file.
Keep scope minimal. A retry must address verification feedback.
FEEDBACK:\n{feedback}\n\n{context}"""
        return self._complete(messages=[{"role": "user", "content": prompt}], max_tokens=self.patch_output_tokens, reasoning_effort=self.patch_reasoning)
