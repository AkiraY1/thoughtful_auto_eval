## harbor_rubric_refine_task

Second-stage Harbor task where the agent:

1. Creates independent agent-side reasoning in `agent_eval.json`.
2. Compares that reasoning to judge reasoning in `output.json`.
3. Writes improvement notes to `agent_notes.md`.
4. Archives previous rubric in `old_rubrics/rubric_vN.json`.
5. Updates `rubric.json` with a refined rubric.
