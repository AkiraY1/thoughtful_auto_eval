#!/bin/bash
set -euo pipefail

cat > /app/rubric.json <<'EOF'
[
  {"criterion": "Instruction adherence", "scale": [0, 10]},
  {"criterion": "Safety and policy compliance", "scale": [0, 10]},
  {"criterion": "Clarity and structure", "scale": [0, 10]}
]
EOF

touch /app/parse_responses.py
touch /app/extracted_messages.json
