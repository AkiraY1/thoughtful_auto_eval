You are designing `rubric.json` for downstream LLM judging. The goal is not "nice wording"; it is high signal, high reliability scoring.

## Output contract (strict)

Write `/app/rubric.json` as a JSON list of objects:

`{"criterion": "<clear single objective>", "scale": [<min>, <max>]}`

Minimum 3 criteria. Keep criteria independent (low overlap).

## Primary inputs to ground the rubric

Use all of these before finalizing:

- `/app/system_prompt.txt` (target behavior and constraints)
- `/app/responses.json` (real data format, noise profile, message style)

Always inspect the first object in `/app/responses.json` first to infer:

- which fields carry useful evidence,
- where common failure modes appear,
- what "good vs bad" looks like in this dataset.

## Rubric design principles (depth-first)

1. **Criterion atomicity**
   - One criterion = one latent construct.
   - Avoid blended criteria like "helpful and factual and concise".
2. **Behavioral anchoring**
   - Each criterion should be scoreable from observable text behavior.
   - No hidden/internal-state criteria.
3. **Mutual distinguishability**
   - Criteria should not be near-duplicates.
   - If two criteria would produce the same score movement, merge or rewrite.
4. **Scale meaning**
   - Use stable numeric ranges with interpretable spread (for example, `[0, 5]` or `[0, 10]`).
   - Keep scales consistent across most criteria unless there is a concrete reason not to.
5. **Coverage of critical objectives**
   - Include key system-prompt requirements: instruction adherence, safety/policy constraints, completeness, and hallucination control (when relevant).
   - Do not include irrelevant dimensions that cannot be observed in responses.
6. **Reliability under multi-rater usage**
   - Ask: would two competent evaluators likely assign similar scores from the same evidence?
   - Reduce ambiguity words ("good", "solid", "decent") in criterion names; use specific, testable wording.

## Recommended creation workflow

1. Read `/app/system_prompt.txt`.
2. Read first object from `/app/responses.json` to infer format/failure modes.
3. Draft 5-8 candidate criteria.
4. Remove overlap and rewrite into atomic criteria.
5. Assign scales.
6. Validate with this checklist:
   - every criterion is observable,
   - every criterion is non-overlapping,
   - scale ranges are numeric and sensible,
   - criteria reflect the target system prompt and dataset format.
7. Write final JSON list to `/app/rubric.json`.

## Quality bar

A strong rubric here should let the deterministic judge produce stable, differentiable per-criterion scores and make downstream refinement easier (not noisier).