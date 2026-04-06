import json
from pathlib import Path

AGENT_NOTES_TEMPLATE = (
    "# Agent Notes (Append Only)\n\n"
    "<!-- APPEND_ONLY_TEMPLATE: do not edit or remove this header block. -->\n\n"
)


def test_required_inputs_exist():
    assert Path("/app/rubric.json").exists()
    assert Path("/app/responses.json").exists()
    assert Path("/app/output.json").exists()


def test_agent_eval_exists():
    assert Path("/app/agent_eval.json").exists()


def test_agent_notes_exists():
    assert Path("/app/agent_notes.md").exists()


def test_agent_notes_append_only():
    notes_path = Path("/app/agent_notes.md")
    content = notes_path.read_text(encoding="utf-8")
    assert content.startswith(AGENT_NOTES_TEMPLATE), (
        "agent_notes.md must preserve the initial template/header exactly."
    )
    appended = content[len(AGENT_NOTES_TEMPLATE) :]
    assert appended.strip(), "agent_notes.md must append new content after the template."


def test_archived_rubric_exists():
    old_rubrics = Path("/app/old_rubrics")
    assert old_rubrics.exists()
    archived = sorted(old_rubrics.glob("rubric_v*.json"))
    assert archived, "Expected at least one archived rubric file in old_rubrics/"


def test_rubric_json_structure_still_valid():
    rubric_path = Path("/app/rubric.json")
    assert rubric_path.exists()
    raw = json.loads(rubric_path.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert len(raw) >= 3
    for idx, item in enumerate(raw):
        assert isinstance(item, dict), f"rubric[{idx}] must be an object"
        assert "criterion" in item, f"rubric[{idx}] missing criterion"
        assert "scale" in item, f"rubric[{idx}] missing scale"
