from __future__ import annotations
import argparse, json, time
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from .llm import MistralAgent
from .models import RunReport, RunStatus
from .patches import apply_patch
from .runner import AgentRunner
from .sandbox import DockerSandbox

def make_runner(attempts: int) -> AgentRunner:
    return AgentRunner(MistralAgent(), DockerSandbox(), attempts)

def main() -> None:
    load_dotenv(); parser = argparse.ArgumentParser(description="Run a sandboxed coding agent"); sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run"); run.add_argument("--repo", required=True, type=Path); run.add_argument("--issue", required=True); run.add_argument("--test", default="pytest -q"); run.add_argument("--attempts", type=int, default=3); run.add_argument("--apply", action="store_true")
    apply_report = sub.add_parser("apply-report", help="Apply an already reviewed, verified report"); apply_report.add_argument("--repo", required=True, type=Path); apply_report.add_argument("--report", default=Path("agent-run.json"), type=Path)
    ev = sub.add_parser("eval"); ev.add_argument("--repo", required=True, type=Path); ev.add_argument("--benchmark", required=True, type=Path); ev.add_argument("--test", default="pytest -q"); ev.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args(); console = Console()
    if args.command == "run":
        report = make_runner(args.attempts).run(args.repo, args.issue, args.test, args.apply); Path("agent-run.json").write_text(report.model_dump_json(indent=2), encoding="utf-8"); console.print_json(report.model_dump_json()); return
    if args.command == "apply-report":
        report = RunReport.model_validate_json(args.report.read_text(encoding="utf-8")); repo = args.repo.resolve()
        if report.status is not RunStatus.REVIEW_READY or not report.verification or not report.verification.passed: parser.error("Report is not a verified, review-ready run; refusing to apply it.")
        if report.repo.resolve() != repo: parser.error("Report repository does not match --repo; refusing to apply it.")
        apply_patch(report.patch, repo); console.print("[green]Applied the exact verified patch from the report.[/green]"); return
    cases, started = json.loads(args.benchmark.read_text(encoding="utf-8")), time.monotonic(); runner = make_runner(args.attempts)
    reports_dir = Path("eval-runs"); reports_dir.mkdir(exist_ok=True)
    results = []
    for case in cases:
        result = runner.run(args.repo, case["issue"], case.get("test_command", args.test))
        (reports_dir / f"{case['id']}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
        results.append(result)
    ready = [result for result in results if result.status == RunStatus.REVIEW_READY]
    summary = {"cases":len(results), "review_ready":len(ready), "resolution_rate":len(ready)/len(results) if results else 0, "average_retries":sum(result.attempts-1 for result in results)/len(results) if results else 0, "elapsed_seconds":round(time.monotonic()-started,2), "reports_dir":str(reports_dir)}
    Path("eval-report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8"); console.print_json(json.dumps(summary))
if __name__ == "__main__": main()