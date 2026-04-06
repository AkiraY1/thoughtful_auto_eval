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


def test_extracted_messages_file_exists():
    extracted_path = Path("/app/extracted_messages.json")
    assert extracted_path.exists(), f"Missing file: {extracted_path}"
