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

## Safety Note

During the blocked batch attempt, an unrelated `ComfyUI` Python process was mistakenly stopped while investigating a suspected hang. Future cleanup must verify PID command lines first and avoid terminating unrelated long-running work.
