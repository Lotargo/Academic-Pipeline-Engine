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

## Run 2026-06-16T03:01:32 - technical_continuation

Date: 2026-06-16
Commit/branch: local working tree
Config snapshot: writer=zen/deepseek-v4-flash-free, reviewer=zen/mimo-v2.5-free, planner=zen/big-pickle, example_generator=zen/deepseek-v4-flash-free
Scenario: Technical document continuation (technical_continuation)
Expected checks: README heading style preserved; no forced academic-paper structure; practical usage content appended; no visible internal planning labels
Stage log: see exports/_smoke JSONL log for full flushed checkpoints.
Result: PASS
Elapsed: 92.8s
Observed imbalance: none
Follow-up: exports\_smoke\20260616_030132\technical_continuation\stage_log.jsonl

## Diagnostic Findings 2026-06-16

- The timed-out `technical_continuation` run was not a silent hang: JSONL heartbeat showed continuous real Zen calls until failure.
- The runner was using default config sections (`theory`, `calculation`, `conclusion`) instead of the continuation source section (`readme`), unlike the API path that aligns continuation structure before orchestration. This caused README continuation to draft academic/default sections.
- Writer self-critique doubled writer calls, and reviewer rejection triggered patch revision plus self-verification loops. The blocked run recorded 48 agent-call starts and 71 heartbeat events before failure.
- The final `OSError` occurred after the outer command timeout while the child process was still logging. The runner now treats stdout as best-effort and keeps JSONL as the source of truth.
- Diagnostic rerun: `technical_continuation --disable-expensive-loops` after source-section alignment completed PASS in 92.8s with real `zen` provider. This does not close the full gate, but it confirms the previous block was caused by smoke harness/configuration and expensive loops, not by an unavoidable provider hang.
- Follow-up: keep source-section alignment in the runner; either run smoke with `--disable-expensive-loops` for gate diagnostics or add bounded per-agent-call timeouts before enabling full self-critique/retry loops.

## Run 2026-06-16T03:08:19 - creative_continuation

Date: 2026-06-16
Commit/branch: local working tree
Config snapshot: writer=zen/deepseek-v4-flash-free, reviewer=zen/mimo-v2.5-free, planner=zen/big-pickle, example_generator=zen/deepseek-v4-flash-free
Scenario: Creative continuation (creative_continuation)
Expected checks: same story rather than restart; no visible exposition/development/red flags headings; source part style preserved; continuation intent and merge metadata present
Stage log: see exports/_smoke JSONL log for full flushed checkpoints.
Result: PASS
Elapsed: 227.4s
Observed imbalance: none
Follow-up: exports\_smoke\20260616_030819\creative_continuation\stage_log.jsonl

## Run 2026-06-16T03:12:34 - creative_bridge

Date: 2026-06-16
Commit/branch: local working tree
Config snapshot: writer=zen/deepseek-v4-flash-free, reviewer=zen/mimo-v2.5-free, planner=zen/big-pickle, example_generator=zen/deepseek-v4-flash-free
Scenario: Creative bridge (creative_bridge)
Expected checks: closed ending bridged or tail replaced; no disconnected branch after hard ending; no visible internal planning labels; merge metadata reflects bridge/append behavior
Stage log: see exports/_smoke JSONL log for full flushed checkpoints.
Result: PASS
Elapsed: 116.6s
Observed imbalance: none
Follow-up: exports\_smoke\20260616_031234\creative_bridge\stage_log.jsonl

## Run 2026-06-16T03:15:07 - school_revision

Date: 2026-06-16
Commit/branch: local working tree
Config snapshot: writer=zen/deepseek-v4-flash-free, reviewer=zen/mimo-v2.5-free, planner=zen/big-pickle, example_generator=zen/deepseek-v4-flash-free
Scenario: School revision (school_revision)
Expected checks: revises in place instead of appending; student-level register preserved; no duplicate essay/introduction/conclusion; intent is revise_in_place
Stage log: see exports/_smoke JSONL log for full flushed checkpoints.
Result: SUPERSEDED
Elapsed: 268.7s
Observed imbalance: runner rubric was too weak: JSONL showed final reviewer rejection on attempt 3/3, but the run was initially recorded as PASS.
Follow-up: exports\_smoke\20260616_031507\school_revision\stage_log.jsonl

## Run 2026-06-16T03:20:20 - school_revision

Date: 2026-06-16
Commit/branch: local working tree
Config snapshot: writer=zen/deepseek-v4-flash-free, reviewer=zen/mimo-v2.5-free, planner=zen/big-pickle, example_generator=zen/deepseek-v4-flash-free
Scenario: School revision (school_revision)
Expected checks: revises in place instead of appending; student-level register preserved; no duplicate essay/introduction/conclusion; intent is revise_in_place
Stage log: see exports/_smoke JSONL log for full flushed checkpoints.
Result: PASS
Elapsed: 182.6s
Observed imbalance: none
Follow-up: exports\_smoke\20260616_032020\school_revision\stage_log.jsonl

## Run 2026-06-16T03:24:05 - academic_references

Date: 2026-06-16
Commit/branch: local working tree
Config snapshot: writer=zen/deepseek-v4-flash-free, reviewer=zen/mimo-v2.5-free, planner=zen/big-pickle, example_generator=zen/deepseek-v4-flash-free
Scenario: Academic/RGR continuation with references (academic_references)
Expected checks: new body appears before references; references remain terminal; bibliography is a single merged section; no editorial 'new sources added' label
Stage log: see exports/_smoke JSONL log for full flushed checkpoints.
Result: BLOCKED
Elapsed: outer command timed out after approximately 5 minutes.
Observed imbalance: intent resolver treated the request as references-only because the instructions mentioned references as a terminal-section constraint.

Cleanup after timed-out academic_references run:
- checked PID 33760: C:\WINDOWS\system32\cmd.exe /c "F:\projects\Academic-Pipeline-Engine\.venv\Scripts\python.exe scripts/continuation_smoke_runner.py academic_references --disable-expensive-loops --heartbeat-seconds 20"
- checked PID 43180: F:\projects\Academic-Pipeline-Engine\.venv\Scripts\python.exe  scripts/continuation_smoke_runner.py academic_references --disable-expensive-loops --heartbeat-seconds 20

## Run 2026-06-16T03:30:39 - academic_references

Date: 2026-06-16
Commit/branch: local working tree
Config snapshot: writer=zen/deepseek-v4-flash-free, reviewer=zen/mimo-v2.5-free, planner=zen/big-pickle, example_generator=zen/deepseek-v4-flash-free
Scenario: Academic/RGR continuation with references (academic_references)
Expected checks: new body appears before references; references remain terminal; bibliography is a single merged section; no editorial 'new sources added' label
Stage log: see exports/_smoke JSONL log for full flushed checkpoints.
Result: BLOCKED
Elapsed: outer command timed out after approximately 5 minutes.
Observed imbalance: merge flow ran, but fixture section bodies duplicated their own visible headings, causing quality gate duplicate introduction/references failures.

Cleanup after second timed-out academic_references run:
- checked PID 2016: C:\WINDOWS\system32\cmd.exe /c "F:\projects\Academic-Pipeline-Engine\.venv\Scripts\python.exe scripts/continuation_smoke_runner.py academic_references --disable-expensive-loops --heartbeat-seconds 20"
- checked PID 41864: F:\projects\Academic-Pipeline-Engine\.venv\Scripts\python.exe  scripts/continuation_smoke_runner.py academic_references --disable-expensive-loops --heartbeat-seconds 20

## Run 2026-06-16T03:37:03 - academic_references

Date: 2026-06-16
Commit/branch: local working tree
Config snapshot: writer=zen/deepseek-v4-flash-free, reviewer=zen/mimo-v2.5-free, planner=zen/big-pickle, example_generator=zen/deepseek-v4-flash-free
Scenario: Academic/RGR continuation with references (academic_references)
Expected checks: new body appears before references; references remain terminal; bibliography is a single merged section; no editorial 'new sources added' label
Stage log: see exports/_smoke JSONL log for full flushed checkpoints.
Result: BLOCKED
Elapsed: outer command timed out after approximately 5 minutes.
Observed imbalance: merge flow ran, but references fixture was shorter than smoke volume threshold and triggered unnecessary revision loops.

Cleanup after third timed-out academic_references run:
- checked PID 21156: C:\WINDOWS\system32\cmd.exe /c "F:\projects\Academic-Pipeline-Engine\.venv\Scripts\python.exe scripts/continuation_smoke_runner.py academic_references --disable-expensive-loops --heartbeat-seconds 20"
- checked PID 15388: F:\projects\Academic-Pipeline-Engine\.venv\Scripts\python.exe  scripts/continuation_smoke_runner.py academic_references --disable-expensive-loops --heartbeat-seconds 20

## Run 2026-06-16T03:43:16 - academic_references

Date: 2026-06-16
Commit/branch: local working tree
Config snapshot: writer=zen/deepseek-v4-flash-free, reviewer=zen/mimo-v2.5-free, planner=zen/big-pickle, example_generator=zen/deepseek-v4-flash-free
Scenario: Academic/RGR continuation with references (academic_references)
Expected checks: new body appears before references; references remain terminal; bibliography is a single merged section; no editorial 'new sources added' label
Stage log: see exports/_smoke JSONL log for full flushed checkpoints.
Result: PASS
Elapsed: 117.3s
Observed imbalance: none
Follow-up: exports\_smoke\20260616_034316\academic_references\stage_log.jsonl

## Run 2026-06-16T09:20:10 - academic_references

Date: 2026-06-16
Commit/branch: local working tree
Config snapshot: writer=zen/deepseek-v4-flash-free, reviewer=zen/mimo-v2.5-free, planner=zen/big-pickle, example_generator=zen/deepseek-v4-flash-free
Scenario: Academic/RGR continuation with references (academic_references)
Expected checks: new body appears before references; references remain terminal; bibliography is a single merged section; no editorial 'new sources added' label
Stage log: see exports/_smoke JSONL log for full flushed checkpoints.
Result: PASS
Elapsed: 203.7s
Observed imbalance: none
Follow-up: exports\_smoke\20260616_092010\academic_references\stage_log.jsonl
