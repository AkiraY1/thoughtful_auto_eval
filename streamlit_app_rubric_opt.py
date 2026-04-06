from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import streamlit as st


REPO_ROOT = Path(__file__).resolve().parent
RUN_SCRIPT = REPO_ROOT / "harbor_scripts" / "run_rubric_opt_task.sh"
JOBS_DIR = REPO_ROOT / "jobs"


def _list_final_optimized_rubrics() -> set[Path]:
    if not JOBS_DIR.exists():
        return set()
    return set(
        JOBS_DIR.glob(
            "**/harbor_rubric_opt_task__*/artifacts/optimization_loop/final/rubric.json"
        )
    )


def run_rubric_opt_task(
    system_prompt: str, dataset_bytes: bytes, iterations: int
) -> tuple[str | None, str]:
    if not RUN_SCRIPT.exists():
        return None, f"Missing run script: {RUN_SCRIPT}"

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None, "ANTHROPIC_API_KEY is not set in the environment."

    before = _list_final_optimized_rubrics()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        prompt_path = tmp / "systemPrompt.txt"
        dataset_path = tmp / "responses.json"

        prompt_path.write_text(system_prompt, encoding="utf-8")
        dataset_path.write_bytes(dataset_bytes)

        completed = subprocess.run(
            [str(RUN_SCRIPT), str(prompt_path), str(dataset_path), str(iterations)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    if completed.returncode != 0:
        output = "\n".join(
            part for part in [completed.stdout.strip(), completed.stderr.strip()] if part
        )
        return None, output or "Task failed with no output."

    after = _list_final_optimized_rubrics()
    new_artifacts = sorted(after - before, key=lambda p: p.stat().st_mtime, reverse=True)

    rubric_path: Path | None = None
    if new_artifacts:
        rubric_path = new_artifacts[0]
    elif after:
        rubric_path = max(after, key=lambda p: p.stat().st_mtime)

    if rubric_path is None:
        return None, "Task completed, but no refined rubric artifact was found in jobs/."

    try:
        rubric_text = rubric_path.read_text(encoding="utf-8")
        # Validate JSON shape lightly before showing.
        parsed = json.loads(rubric_text)
        if not isinstance(parsed, list):
            return None, f"Refined rubric exists but is not a JSON list: {rubric_path}"
        return json.dumps(parsed, indent=2), ""
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Could not read refined rubric JSON: {exc}"


def main() -> None:
    st.set_page_config(page_title="Rubric Optimizer", layout="wide")
    st.title("Rubric Optimizer (harbor_rubric_opt_task)")
    st.write(
        "Provide a system prompt and upload a JSON dataset. The pipeline runs rubric creation, deterministic judging, and refinement, then returns the optimized `rubric.json`."
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

    uploaded_json = st.file_uploader(
        "Upload responses JSON (top-level list)", type=["json"]
    )
    iterations = st.number_input(
        "Optimization iterations",
        min_value=1,
        max_value=20,
        value=2,
        step=1,
        help="Number of judge->refine loop iterations to run.",
    )

    run_clicked = st.button("Run rubric_opt_task", type="primary", use_container_width=True)

    if run_clicked:
        prompt = system_prompt.strip()
        if not prompt:
            st.error("Please provide a non-empty system prompt.")
            return
        if uploaded_json is None:
            st.error("Please upload a JSON file.")
            return

        dataset_bytes = uploaded_json.getvalue()
        if not dataset_bytes:
            st.error("Uploaded JSON file is empty.")
            return

        with st.spinner("Running rubric_opt_task pipeline... this can take a while."):
            rubric_json_text, error = run_rubric_opt_task(
                prompt, dataset_bytes, int(iterations)
            )

        if error:
            st.error("rubric_opt_task failed.")
            st.code(error)
            return

        st.success("Optimized rubric generated.")
        st.subheader("Optimized rubric.json (raw)")
        st.code(rubric_json_text or "", language="json")


if __name__ == "__main__":
    main()
