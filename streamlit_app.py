from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import streamlit as st


REPO_ROOT = Path(__file__).resolve().parent
RUN_SCRIPT = REPO_ROOT / "harbor_scripts" / "run_rubric_task.sh"
JOBS_DIR = REPO_ROOT / "jobs"


def _list_rubric_artifacts() -> set[Path]:
    if not JOBS_DIR.exists():
        return set()
    return set(JOBS_DIR.glob("**/artifacts/rubric.txt"))


def run_rubric_task(system_prompt: str) -> tuple[str | None, str]:
    if not RUN_SCRIPT.exists():
        return None, f"Missing script: {RUN_SCRIPT}"

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None, "ANTHROPIC_API_KEY is not set in the environment."

    before = _list_rubric_artifacts()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp_file:
        tmp_file.write(system_prompt)
        tmp_path = Path(tmp_file.name)

    try:
        completed = subprocess.run(
            [str(RUN_SCRIPT), str(tmp_path)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    if completed.returncode != 0:
        output = "\n".join(
            part for part in [completed.stdout.strip(), completed.stderr.strip()] if part
        )
        return None, output or "Task failed with no output."

    after = _list_rubric_artifacts()
    new_artifacts = sorted(after - before, key=lambda p: p.stat().st_mtime, reverse=True)

    rubric_path: Path | None = None
    if new_artifacts:
        rubric_path = new_artifacts[0]
    elif after:
        rubric_path = max(after, key=lambda p: p.stat().st_mtime)

    if rubric_path is None:
        return None, "Task completed, but no rubric artifact was found in jobs/."

    try:
        return rubric_path.read_text(encoding="utf-8"), ""
    except OSError as exc:
        return None, f"Could not read generated rubric: {exc}"


def main() -> None:
    st.set_page_config(page_title="Rubric Task Runner", layout="centered")
    st.title("Rubric Task Runner")
    st.write(
        "Enter a system prompt, run `rubric_task`, and view the generated `rubric.txt` artifact."
    )

    default_prompt = (
        "You are a concise assistant. Follow user instructions while staying factual and safe."
    )
    system_prompt = st.text_area(
        "System prompt",
        value=default_prompt,
        height=220,
        placeholder="Write the system prompt to evaluate against...",
    )

    run_clicked = st.button("Run rubric_task", type="primary", use_container_width=True)

    if run_clicked:
        prompt = system_prompt.strip()
        if not prompt:
            st.error("Please provide a non-empty system prompt.")
            return

        with st.spinner("Running rubric_task... this can take a while."):
            rubric_text, error = run_rubric_task(prompt)

        if error:
            st.error("rubric_task failed.")
            st.code(error)
            return

        st.success("Rubric generated.")
        st.subheader("Generated rubric.txt")
        st.text_area("Rubric", value=rubric_text or "", height=350)


if __name__ == "__main__":
    main()
