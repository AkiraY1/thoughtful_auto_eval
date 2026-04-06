#!/bin/bash
set -euo pipefail

cp /app/rubric.json /app/old_rubrics/rubric_v0.json

cat > /app/agent_eval.json <<'EOF'
[
  {
    "item_index": 0,
    "notes": "Reference solution placeholder agent evaluation."
  }
]
EOF

cat >> /app/agent_notes.md <<'EOF'
- Placeholder notes appended by reference solution.
EOF

python3 - <<'EOF'
import json
from pathlib import Path

path = Path("/app/change_summary.json")
if path.exists():
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        data = []
else:
    data = []

data.append(
    {
        "iteration": len(data) + 1,
        "changes": [
            "Clarified one key criterion wording.",
            "Adjusted one scale range for better discrimination.",
        ],
    }
)
path.write_text(json.dumps(data, indent=2), encoding="utf-8")
EOF
