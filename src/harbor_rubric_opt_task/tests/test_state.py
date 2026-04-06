import json
from pathlib import Path


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_inputs_exist():
    assert Path("/app/system_prompt.txt").exists()
    assert Path("/app/responses.json").exists()
    assert Path("/app/llm_api.py").exists()


def test_rubric_file_exists_and_not_empty():
    rubric_path = Path("/app/rubric.txt")
    assert rubric_path.exists(), f"Missing file: {rubric_path}"
    assert rubric_path.read_text(encoding="utf-8").strip(), "rubric.txt is empty"


def test_parser_script_exists():
    parser_path = Path("/app/parse_responses.py")
    assert parser_path.exists(), f"Missing file: {parser_path}"
    assert parser_path.read_text(encoding="utf-8").strip(), "parse_responses.py is empty"


def test_parsed_responses_file_structure():
    parsed_path = Path("/app/parsed_responses.json")
    assert parsed_path.exists(), f"Missing file: {parsed_path}"
    parsed = _read_json(parsed_path)
    assert isinstance(parsed, list), "parsed_responses.json must be a JSON list"
    assert len(parsed) > 0, "parsed_responses.json must contain at least one extracted response"

    for idx, item in enumerate(parsed):
        assert isinstance(item, dict), f"parsed_responses[{idx}] must be an object"
        assert "response_id" in item, f"parsed_responses[{idx}] missing response_id"
        assert "response_text" in item, f"parsed_responses[{idx}] missing response_text"
        assert str(item["response_text"]).strip(), f"parsed_responses[{idx}] response_text is empty"


def test_judgments_exist_for_each_response():
    parsed = _read_json(Path("/app/parsed_responses.json"))
    judged_path = Path("/app/judged_responses.json")
    assert judged_path.exists(), f"Missing file: {judged_path}"
    judged = _read_json(judged_path)
    assert isinstance(judged, list), "judged_responses.json must be a JSON list"
    assert len(judged) == len(parsed), "Must produce one judgment per parsed response"

    seen_ids = set()
    for idx, item in enumerate(judged):
        assert isinstance(item, dict), f"judged_responses[{idx}] must be an object"
        assert "response_id" in item, f"judged_responses[{idx}] missing response_id"
        assert "response_text" in item, f"judged_responses[{idx}] missing response_text"
        assert "judge_output" in item, f"judged_responses[{idx}] missing judge_output"
        assert str(item["judge_output"]).strip(), f"judged_responses[{idx}] judge_output is empty"
        response_id = str(item["response_id"])
        assert response_id not in seen_ids, f"Duplicate response_id found: {response_id}"
        seen_ids.add(response_id)

    parsed_ids = {str(item["response_id"]) for item in parsed}
    assert seen_ids == parsed_ids, "Judged response IDs must exactly match parsed response IDs"
