from pathlib import Path


def test_inputs_exist():
    assert Path("/app/system_prompt.txt").exists()
    assert Path("/app/responses.json").exists()
    assert Path("/app/llm_api.py").exists()


def test_rubric_file_exists():
    rubric_path = Path("/app/rubric.txt")
    assert rubric_path.exists(), f"Missing file: {rubric_path}"


def test_parser_script_exists():
    parser_path = Path("/app/parse_responses.py")
    assert parser_path.exists(), f"Missing file: {parser_path}"


def test_parsed_responses_file_exists():
    parsed_path = Path("/app/parsed_responses.json")
    assert parsed_path.exists(), f"Missing file: {parsed_path}"


def test_judged_responses_file_exists():
    judged_path = Path("/app/judged_responses.json")
    assert judged_path.exists(), f"Missing file: {judged_path}"
