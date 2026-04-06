from pathlib import Path


def test_system_prompt_exists():
    system_prompt_path = Path("/app/system_prompt.txt")
    assert system_prompt_path.exists(), f"File {system_prompt_path} does not exist"


def test_rubric_file_exists():
    rubric_path = Path("/app/rubric.txt")
    assert rubric_path.exists(), f"File {rubric_path} does not exist"


def test_rubric_file_not_empty():
    rubric_path = Path("/app/rubric.txt")
    content = rubric_path.read_text().strip()
    assert content, "rubric.txt is empty"
