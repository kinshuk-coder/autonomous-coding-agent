from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

from .context import build_context
from .llm import GeminiAgent
from .models import RunReport, RunStatus, VerificationReport
from .observability import RunStore
from .patches import UnsafePatch, apply_patch, normalize_patch
from .sandbox import DockerSandbox


class AgentRunner:
    def __init__(self, llm: GeminiAgent, sandbox: DockerSandbox, max_attempts: int = 3) -> None:
        self.llm, self.sandbox, self.max_attempts = llm, sandbox, max_attempts

    def run(self, repo: Path, issue: str, test_command: str, apply: bool = False) -> RunReport:
        repo = repo.resolve()
        run_id, store = str(uuid.uuid4()), RunStore(repo)
        context = build_context(repo, issue)
        plan = self.llm.plan(context, test_command)
        store.log(run_id, "plan", plan.model_dump())
        if not plan.in_scope:
            return RunReport(run_id=run_id, status=RunStatus.REJECTED, confidence=0, plan=plan, attempts=0, repo=repo, escalation_reason=plan.scope_reason)
        feedback, signatures, patch, report = "", set(), "", None
        for attempt in range(1, self.max_attempts + 1):
            worktree = repo.parent / f".agent-worktree-{run_id[:8]}-{attempt}"
            shutil.copytree(repo, worktree, ignore=shutil.ignore_patterns(".git", ".agent", ".venv", "__pycache__"))
            try:
                patch = normalize_patch(self.llm.patch(context, plan, feedback))
                try:
                    apply_patch(patch, worktree)
                except UnsafePatch as error:
                    feedback = f"Patch rejected: {error}"
                    store.log(run_id, "patch_rejected", feedback)
                    continue
                result = self.sandbox.run(worktree, plan.test_command or test_command)
                signature = hashlib.sha256((result.stderr + result.stdout)[-2000:].encode()).hexdigest()[:12]
                report = VerificationReport(passed=result.exit_code == 0, commands=[result], failure_signature=signature if result.exit_code else "")
                store.log(run_id, "verification", report.model_dump())
                if report.passed:
                    if apply:
                        apply_patch(patch, repo)
                    return RunReport(run_id=run_id, status=RunStatus.REVIEW_READY, confidence=round(.95 - .1 * (attempt - 1), 2), plan=plan, patch=patch, attempts=attempt, verification=report, repo=repo)
                if signature in signatures:
                    return RunReport(run_id=run_id, status=RunStatus.ESCALATED, confidence=.2, plan=plan, patch=patch, attempts=attempt, verification=report, repo=repo, escalation_reason="Repeated verification failure; stopping to avoid blind retries.")
                signatures.add(signature)
                feedback = f"Verification failed (exit {result.exit_code}):\n{result.stderr[-4000:]}\n{result.stdout[-2000:]}"
            finally:
                shutil.rmtree(worktree, ignore_errors=True)
        return RunReport(run_id=run_id, status=RunStatus.ESCALATED, confidence=.3, plan=plan, patch=patch, attempts=self.max_attempts, verification=report, repo=repo, escalation_reason="Retry budget exhausted; requires human review.")
