# Notes and Lessons Learned

This file captures the key lessons learned while building and iterating on the Harbor rubric optimization workflow.

## 1) Pipeline architecture lessons

- Splitting the workflow into explicit stages made debugging easier:
  - rubric creation (`harbor_rubric_opt_task`)
  - deterministic judge (`src/deterministic_judge.py`)
  - rubric refinement (`harbor_rubric_refine_task`)
- Keeping stage outputs as explicit artifacts reduced ambiguity and made state transitions traceable.
- Iterative optimization loops are easier to reason about when each iteration has its own folder and fixed filenames.

## 2) Harbor task design lessons

- Task instructions must be very explicit when output format matters.
- Verifiers should enforce only what is truly required; over-constraining tests causes brittle behavior.
- When requiring append-only behavior, provide:
  - an initial template file
  - explicit instruction wording
  - verifier checks that the prefix/header is preserved
- For history/versioning requirements, define deterministic naming and ordering (`rubric_v0`, `rubric_v1`, ...).

## 3) Deterministic judge lessons

- Judge inputs and parser expectations must be aligned:
  - passing an already-extracted file where raw dataset is expected causes empty outputs.
- Two-turn criterion evaluation (reasoning then score) gives better auditability than single-turn scoring.
- Scoring criterion-by-criterion and summing is clearer and easier to debug than one monolithic score.
- Parallelizing item-level judging improves throughput significantly.
- Keep output structured:
  - per-criterion reasoning
  - per-criterion score
  - final summed score

## 4) State management lessons

- Stateful files should be carried via explicit artifacts, not implicit container state.
- Stable output paths are critical for downstream tooling/UI:
  - `jobs/latest_harbor_rubric_refine_artifacts/`
  - pointer file: `jobs/latest_harbor_rubric_refine_artifacts.txt`
- Beginning each top-level run from a clean slate prevents stale state contamination:
  - clear stateful environment files
  - clear local stable mirrors/pointers

## 5) Build and environment lessons

- `--force-build` is expensive and can dominate runtime in iterative loops.
- Removing `--force-build` usually speeds up loops via image cache reuse.
- If Dockerfile `COPY` paths are required, ensure files/dirs always exist before Harbor run.
- Empty directories can be fragile in build contexts; `.gitkeep` style placeholders are useful.

## 6) Reliability and failure-surfacing lessons

- A script can appear "done" even when a substage failed if exit handling is not strict.
- Always parse/check trial result files (`result.json`) and fail hard on exceptions.
- Always verify required artifact existence after each stage.
- Small shell typos at EOF can invalidate otherwise successful runs (`unexpected EOF`, stray command chars).

## 7) Change tracking lessons

- `agent_notes.md` should be append-only and read-before-write to preserve prior context.
- `change_summary.json` needs a strict schema to prevent drift.
- For iterative loops, enforce exactly one changelog entry per iteration:
  - key/value map shape like:
    - `{ "0": [...], "1": [...] }`
- Update changelog only at the end of refinement after rubric edits are finalized.

## 8) Streamlit UX lessons

- Two-column layout improves observability:
  - left: inputs + controls
  - right: live outputs
- Showing logs in the page is optional; many users prefer cleaner UI without log spam.
- Live iteration-aware updates are better than final-only rendering:
  - change summary updates after each completed iteration
  - per-iteration rubric before/after snapshots
  - final rubric at completion
- Progress indicators are essential for long loops:
  - progress bar by iterations completed
  - ETA from a simple per-iteration assumption
  - timing breakdowns per iteration

## 9) Performance lessons

- Biggest runtime costs came from agent refinement trial startup/build and model latency.
- Key speed levers:
  - avoid forced builds
  - use faster model where quality allows (e.g., Sonnet-tier for refinement)
  - lower token budgets when possible
  - parallelize deterministic judge calls
- Measuring timing per iteration and per phase (judge vs refine) reveals true bottlenecks.

## 10) Rubric quality lessons

- Rubrics work best when criteria are:
  - atomic (single objective)
  - observable in response text
  - minimally overlapping
  - behaviorally anchored
- Refinement quality improves when using disagreement evidence:
  - compare independent agent eval vs judge reasoning criterion-by-criterion
  - preserve criteria that already agree
  - only modify criteria with repeated disagreement patterns

## 11) Operational lessons

- Keep runner scripts deterministic and explicit:
  - print input hashes to prove which files were used
  - keep per-iteration artifacts under one run folder
  - produce final pointer/metadata outputs for downstream consumers
- Prefer predictable, machine-readable structures for long workflows:
  - iteration folders
  - timing JSON
  - summary JSON
  - stable latest mirror directory

## 12) Practical defaults to keep

- Start from fresh state at each top-level run.
- Use explicit artifact checks after every Harbor stage.
- Preserve append-only files with verifier-backed contracts.
- Track iteration timing and change summaries as first-class outputs.
- Keep final outputs easy to locate:
  - `optimization_loop/final/rubric.json`
  - `optimization_loop/final/change_summary.json`
  - `optimization_loop/final/metadata.json`
