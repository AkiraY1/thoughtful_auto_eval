import json
from pathlib import Path


def test_inputs_exist():
    assert Path("/app/system_prompt.txt").exists()
    assert Path("/app/responses.json").exists()
    assert Path("/app/llm_api.py").exists()


def test_rubric_json_exists_and_has_criteria_schema():
    rubric_path = Path("/app/rubric.json")
    assert rubric_path.exists(), f"Missing file: {rubric_path}"
    raw = json.loads(rubric_path.read_text(encoding="utf-8"))
    assert isinstance(raw, list), "rubric.json must be a JSON list"
    assert len(raw) >= 3, "rubric.json must contain at least 3 criteria objects"

    for idx, item in enumerate(raw):
        assert isinstance(item, dict), f"rubric[{idx}] must be an object"
        assert "criterion" in item, f"rubric[{idx}] missing 'criterion'"
        assert "scale" in item, f"rubric[{idx}] missing 'scale'"
