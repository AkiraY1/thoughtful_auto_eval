Create two outputs in `/app`:

1. `rubric.txt`: a rubric for evaluating how well responses align with `system_prompt.txt`.
2. `parse_responses.py`: a Python script that reads `responses.json` and extracts each response individually.

Requirements:
- You have a skill named `rubric_creation`; use it to guide rubric quality.
- `parse_responses.py` must run with the standard command `python3 parse_responses.py` (no CLI args required).
- The script must produce no stdout/stderr output during normal success.
- The script must write exactly one output file named `extracted_messages.json`.
- `extracted_messages.json` must be a JSON list of `messages` entries in OpenAI-style format (each message has fields like `role` and `content`).
- Before finishing, run `python3 parse_responses.py` once in `/app` to smoke-test the parser and ensure `extracted_messages.json` is created.
