# Continuation Real Smoke Bench Notes

Date: 2026-06-16
Commit/branch: local working tree
Config snapshot: writer=zen/deepseek-v4-flash-free, reviewer=zen/mimo-v2.5-free, planner=zen/big-pickle, example_generator=zen/deepseek-v4-flash-free
Secrets: zen configured; keys not recorded.

## Run Attempt 1

Result: BLOCKED
Elapsed: timed out after approximately 10 minutes
Scenario coverage: runner attempted the required short suite, but did not complete before timeout and produced no reliable per-scenario results.
Observed imbalance: current real-provider smoke flow is too slow/heavy to run as one synchronous 5-scenario pass with the configured provider/models.
Follow-up: split the smoke bench into one scenario per command or add a dedicated bounded smoke runner with per-scenario timeout, progress flushing, and optional planner/topic-refinement bypass.

## Required Runner Correction

- Run exactly one scenario per command.
- Before each scenario, write and flush a note with scenario id, provider/model snapshot, start time, and expected checks.
- During each scenario, log and flush every stage transition and agent call boundary: planning, merge-operation drafting, section drafting, reviewing, revision, quality gate, assembly, and export/preview check when applicable.
- For every agent call, log only safe metadata: agent name, provider name, model name, stage, elapsed seconds, and completion/error status. Do not log prompts containing secrets or full generated documents unless separately sanitized.
- Emit heartbeat/progress timestamps for long provider calls so slow model work is not mistaken for a hang.
- Stop a process only after checking and recording that its command line belongs to the smoke runner for this repository. Do not stop unrelated Python processes based only on CPU time or process name.

## Runner Added

Command format:

```powershell
python scripts/continuation_smoke_runner.py creative_continuation
python scripts/continuation_smoke_runner.py creative_bridge
python scripts/continuation_smoke_runner.py school_revision
python scripts/continuation_smoke_runner.py academic_references
python scripts/continuation_smoke_runner.py technical_continuation
```

The runner executes exactly one scenario per command, appends a concise result to this note, and writes flushed stage/agent-call JSONL logs under `exports/_smoke/`. Logs include provider/model names, elapsed time, stage transitions, agent-call start/end/error, and heartbeat events. Prompts, secrets, and full generated documents are intentionally not logged.

## Safety Note

During the blocked batch attempt, an unrelated `ComfyUI` Python process was mistakenly stopped while investigating a suspected hang. Future cleanup must verify PID command lines first and avoid terminating unrelated long-running work.

## Run 2026-06-16T02:40:23 - technical_continuation

Date: 2026-06-16
Commit/branch: local working tree
Config snapshot: writer=zen/deepseek-v4-flash-free, reviewer=zen/mimo-v2.5-free, planner=zen/big-pickle, example_generator=zen/deepseek-v4-flash-free
Scenario: Technical document continuation (technical_continuation)
Expected checks: README heading style preserved; no forced academic-paper structure; practical usage content appended; no visible internal planning labels
Stage log: see exports/_smoke JSONL log for full flushed checkpoints.

Cleanup after timed-out technical_continuation run:
Result: BLOCKED
Elapsed: approximately 15.7 minutes before scenario_error was recorded; outer command timed out at approximately 15 minutes.
Observed imbalance: single technical_continuation scenario reached DRAFTING with heartbeat/progress logs, then failed before rubric checks with OSError after repeated real Zen calls.
Follow-up: inspect exports/_smoke/20260616_024023/technical_continuation/stage_log.jsonl; add per-agent-call timeout or reduce self-critique/revision loop for smoke mode before attempting the remaining scenarios.
Post-cleanup verification: no remaining continuation_smoke_runner.py processes for this repository were found.
