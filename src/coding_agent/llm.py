from __future__ import annotations

import json
import os

from google import genai
from google.genai import types

from .models import Plan


class GeminiAgent:
    """Small adapter around the official Google Gen AI SDK."""

    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set. Add it to your .env file.")
        self.client = genai.Client(api_key=api_key)
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

    def plan(self, context: str, test_command: str) -> Plan:
        prompt = f'''You are a cautious software engineering planner. Reject vague or broad tasks by setting in_scope false. Make a small, testable plan. Respect the existing repository structure and test conventions shown in context. Default test command: {test_command}\n\n{context}'''
        response = self.client.models.generate_content(
            model=self.model, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=Plan.model_json_schema()),
        )
        return Plan.model_validate(json.loads(response.text or "{}"))

    def patch(self, context: str, plan: Plan, feedback: str = "") -> str:
        prompt = f"""You are a coding agent. Produce ONLY a unified diff, never prose.
Implement this plan: {plan.model_dump_json()}
Respect the repository layout shown in context. Do not invent a top-level `src` Python package: in a Python src-layout project tests import the concrete package name (for example `coding_agent`), not `src.*`.
Keep scope minimal. A retry must address the verification feedback below.
FEEDBACK:\n{feedback}\n\n{context}"""
        response = self.client.models.generate_content(model=self.model, contents=prompt, config=types.GenerateContentConfig(temperature=0))
        return response.text or ""
