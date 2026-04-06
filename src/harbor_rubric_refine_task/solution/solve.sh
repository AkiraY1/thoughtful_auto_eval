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
