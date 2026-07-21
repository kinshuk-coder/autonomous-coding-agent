from __future__ import annotations
import json, os, time
from mistralai.client import Mistral
from .models import Plan
from .rate_limit import TokenRateLimiter

class MistralAgent:
    """Mistral client with RPS/TPM pacing and 429-aware exponential backoff."""
    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key: raise RuntimeError("MISTRAL_API_KEY is not set. Add it to your .env file.")
        self.client = Mistral(api_key=api_key); self.model = model or os.getenv("MISTRAL_MODEL", "mistral-medium-3-5")
        rps = float(os.getenv("MISTRAL_RPS", "0.83"))
        if rps <= 0: raise ValueError("MISTRAL_RPS must be greater than zero")
        self.min_interval_seconds, self.max_retries, self.next_request_at = 1 / rps, int(os.getenv("MISTRAL_MAX_RETRIES", "4")), 0.0
        self.output_token_reserve = int(os.getenv("MISTRAL_OUTPUT_TOKEN_RESERVE", "2000")); self.token_limiter = TokenRateLimiter(int(os.getenv("MISTRAL_TPM", "25000")))
    def _estimate_tokens(self, messages: object) -> int:
        contents = [str(message.get("content", "")) for message in messages if isinstance(message, dict)]
        return max(1, (sum(len(content) for content in contents) + 3) // 4 + self.output_token_reserve)
    def _complete(self, **kwargs: object) -> str:
        self.token_limiter.reserve(self._estimate_tokens(kwargs.get("messages", [])))
        for attempt in range(self.max_retries + 1):
            wait = self.next_request_at - time.monotonic()
            if wait > 0: time.sleep(wait)
            self.next_request_at = time.monotonic() + self.min_interval_seconds
            try:
                response = self.client.chat.complete(**kwargs)
                return response.choices[0].message.content or ""
            except Exception as error:
                limited = getattr(error, "status_code", None) == 429 or "429" in str(error)
                if not limited or attempt == self.max_retries: raise
                self.next_request_at = max(self.next_request_at, time.monotonic() + max(self.min_interval_seconds, 2 ** attempt))
        raise RuntimeError("Unreachable retry state")
    def plan(self, context: str, test_command: str) -> Plan:
        prompt = f'''You are a cautious software engineering planner. Return only a JSON object matching this schema: {{"summary":str,"in_scope":bool,"scope_reason":str,"steps":[{{"id":str,"description":str,"target_files":[str],"acceptance_criteria":[str]}}],"test_command":str}}. Reject vague or broad tasks by setting in_scope false. Make a small, testable plan. Respect existing repository structure and test conventions. Default test command: {test_command}\n\n{context}'''
        content = self._complete(model=self.model, messages=[{"role":"user", "content":prompt}], response_format={"type":"json_object"}, temperature=0)
        return Plan.model_validate(json.loads(content))
    def patch(self, context: str, plan: Plan, feedback: str = "") -> str:
        prompt = f"""You are a coding agent. Produce ONLY an applicable Git unified diff, never prose or Markdown fences.
Implement this plan: {plan.model_dump_json()}
The existing tests in context are the acceptance oracle. Do not modify test files when they already cover this behavior; patch the production source only.
For every modified existing file, begin with exactly `diff --git a/PATH b/PATH`, followed by `--- a/PATH` and `+++ b/PATH`. Include exact unchanged context from the supplied source. Do not represent an existing file as a new file.
Respect the repository layout shown in context. Do not invent a top-level `src` Python package: in a Python src-layout project tests import the concrete package name (for example `coding_agent`), not `src.*`.
Keep scope minimal. A retry must address verification feedback.
FEEDBACK:\n{feedback}\n\n{context}"""
        return self._complete(model=self.model, messages=[{"role":"user", "content":prompt}], temperature=0)
