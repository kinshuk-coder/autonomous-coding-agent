# Resume-ready project description

**Autonomous Coding Agent with Sandboxed Execution** | Python, Groq API, Docker, SQLite

- Built a safety-first autonomous coding agent that converts issue text into structured implementation plans and minimal unified-diff patches.
- Isolated verification in ephemeral Docker containers with network disabled, CPU/memory/PID caps, a read-only root filesystem, and command timeouts.
- Implemented test-feedback self-correction with capped retries, repeated-failure detection, confidence scoring, and an explicit human-review escalation gate.
- Added SQLite event telemetry and a JSON benchmark harness to measure resolution rate, retry count, and latency; replace placeholders with results from your own benchmark run.

Suggested metric format after evaluation: “Achieved **X% review-ready resolution** across **Y issues**, averaging **Z retries** per run.”
