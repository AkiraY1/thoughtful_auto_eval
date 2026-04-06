Create two outputs in `/app`:

1. `rubric.txt`: a rubric for evaluating how well responses align with `system_prompt.txt`.
2. `parse_responses.py`: a Python script that reads `responses.json` and extracts each response individually.

Requirements:
- You have a skill named `rubric_creation`; use it to guide rubric quality.
- `parse_responses.py` should accept CLI args:
  - `--input` for the source dataset JSON path
  - `--output` for where to write extracted responses JSON
- The extracted output should be a JSON list with one entry per response.
