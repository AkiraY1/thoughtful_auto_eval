Rubric refinement is an evidence-based update loop, not a rewrite from scratch.

You are refining `/app/rubric.json` using disagreement evidence between:

- deterministic judge outputs (`/app/output.json`)
- independent agent analysis (`/app/agent_eval.json`, which you create)

and historical context:

- `/app/agent_notes.md` (append-only history)
- `/app/change_summary.json` (append-only change log)
- `/app/old_rubrics/rubric_v*.json` (archived prior rubrics)
- `/app/responses.json` (ground-truth data format and content)

## Refinement goals

1. Improve scoring reliability (less ambiguous interpretation).
2. Improve validity (criteria measure target behavior from system prompt + dataset).
3. Preserve working parts of rubric; edit only where evidence indicates failure.

## Required evidence workflow

1. Read current `/app/rubric.json`.
2. Read prior context:
   - `/app/agent_notes.md`
   - `/app/change_summary.json`
   - latest archived rubric in `/app/old_rubrics/` if present
3. Compare `/app/output.json` vs your own criterion-level reasoning.
4. Identify disagreement patterns:
   - systematic over/under-scoring,
   - criterion overlap,
   - underspecified criterion wording,
   - scale compression (scores clustering without discrimination).
5. Decide minimal rubric edits that address those patterns.

## What to change (and what not to)

- **Change** criteria that repeatedly cause disagreement or ambiguous scoring.
- **Keep** criteria that already align across judge and agent reasoning.
- **Avoid** large wholesale rewrites unless evidence shows broad rubric failure.
- **Keep scales stable** unless scale bounds are clearly uninformative.

## Concrete rubric rewrite guidance

For each modified criterion:

- tighten wording to one observable behavior,
- remove vague terms,
- ensure it can be scored from response text alone,
- preserve JSON schema: `{"criterion": "...", "scale": [min, max]}`.

Ensure final `/app/rubric.json` remains a list with at least 3 criteria.

## Notes + change logging discipline

- Append to `/app/agent_notes.md` (do not edit/remove existing header/history):
  - what judge got right,
  - what judge got wrong,
  - why rubric changes are needed.
- Append one new entry to `/app/change_summary.json` with 2-3 concise bullets describing the highest-impact rubric edits.

## Archival discipline

Before overwriting `/app/rubric.json`, archive previous rubric to `/app/old_rubrics/rubric_vN.json` where `N` is next chronological version.

## Final self-check before finishing

- Append-only constraints respected (`agent_notes.md`, `change_summary.json`).
- Archive created in `/app/old_rubrics/`.
- Updated `/app/rubric.json` is valid JSON list of `{criterion, scale}` objects.
- Changes are evidence-backed by observed disagreement, not stylistic preference.
