Using `rubric.json`, `responses.json`, and `output.json` in `/app`, do rubric refinement.

You must produce these files:

1. `agent_eval.json`
   - Your own independent reasoning about the data and criteria.
2. `agent_notes.md`
   - Compare your reasoning to the LLM judge reasoning in `output.json`.
   - State what judge reasoning is correct, what should be improved, and rubric changes needed.
   - This file is append-only: keep the existing template/header content intact and only add new notes after it.
3. `old_rubrics/rubric_vN.json`
   - Archive the old rubric in chronological version order (`v0`, `v1`, `v2`, ...).
4. Updated `rubric.json`
   - Refine the rubric to better match your notes.
5. `change_summary.json`
   - Update this file ONLY at the end of the refinement process (after rubric edits are finalized).
   - Add exactly one new iteration changelog entry per refinement iteration.
   - Preserve all existing entries unchanged.
   - Required JSON structure:
     - `{"0": ["changed xyz", "modified abc", "tweaked xyz"], "1": [...]}`
   - Keys are iteration indices (as strings), and each value is a list of 2-3 succinct bullet points describing the most important rubric changes.

Requirements:
- Use installed skills to improve rigor and consistency.
- Keep `rubric.json` as a JSON list of objects with keys `criterion` and `scale`.
- Ensure the archived file is inside `old_rubrics/`.
- `agent_notes.md` must remain append-only relative to the initial template provided in `/app/agent_notes.md`.
- Before making rubric changes, read the existing `agent_notes.md` content to understand prior analysis and decisions, then append your new findings after that context.
- `change_summary.json` is append-only across iterations: add exactly one new key for the current iteration, do not rewrite or reorder prior keys.
