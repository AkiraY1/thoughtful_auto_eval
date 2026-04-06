Create one output in `/app`:

1. `rubric.json`: a rubric for evaluating how well responses align with `system_prompt.txt`.

Requirements:
- You have a skill named `rubric_creation`; use it to guide rubric quality.
- `rubric.json` must be a JSON list of criteria objects in this shape:
  - `{"criterion": "<text>", "scale": [<min_score>, <max_score>]}`
- Include multiple criteria (at least 3).
- Each `criterion` must be non-empty text.
- Each `scale` must be two numbers where min < max.
- Inspect the first object in `responses.json` before writing the rubric to understand dataset structure (fields, message layout, and response style), and use that information to make criteria specific to this dataset format.
