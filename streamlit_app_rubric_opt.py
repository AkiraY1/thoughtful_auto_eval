from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

import streamlit as st


REPO_ROOT = Path(__file__).resolve().parent
RUN_SCRIPT = REPO_ROOT / "harbor_scripts" / "run_rubric_opt_task.sh"
JOBS_DIR = REPO_ROOT / "jobs"
STABLE_REFINE_DIR = JOBS_DIR / "latest_harbor_rubric_refine_artifacts"


def _list_final_optimized_rubrics() -> set[Path]:
    if not JOBS_DIR.exists():
        return set()
    return set(
        JOBS_DIR.glob(
            "**/harbor_rubric_opt_task__*/artifacts/optimization_loop/final/rubric.json"
        )
    )


def _read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _get_latest_change_summary() -> Any | None:
    return _read_json(STABLE_REFINE_DIR / "change_summary.json")


def run_rubric_opt_task(
    system_prompt: str,
    dataset_bytes: bytes,
    iterations: int,
    on_output_line: Callable[[str], None] | None = None,
    on_iteration_complete: Callable[[], None] | None = None,
) -> tuple[str | None, Any | None, str]:
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

        cmd = [str(RUN_SCRIPT), str(prompt_path), str(dataset_path), str(iterations)]
        process = subprocess.Popen(
            cmd,
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        assert process.stdout is not None
        output_lines: list[str] = []
        for line in process.stdout:
            stripped = line.rstrip("\n")
            output_lines.append(stripped)
            if on_output_line is not None:
                on_output_line(stripped)
            if "] Completed." in stripped and on_iteration_complete is not None:
                on_iteration_complete()
        process.wait()

    if process.returncode != 0:
        output = "\n".join(output_lines).strip()
        return None, None, output or "Task failed with no output."

    after = _list_final_optimized_rubrics()
    new_artifacts = sorted(after - before, key=lambda p: p.stat().st_mtime, reverse=True)

    rubric_path: Path | None = None
    if new_artifacts:
        rubric_path = new_artifacts[0]
    elif after:
        rubric_path = max(after, key=lambda p: p.stat().st_mtime)

    if rubric_path is None:
        return (
            None,
            None,
            "Task completed, but no refined rubric artifact was found in jobs/.",
        )

    try:
        rubric_text = rubric_path.read_text(encoding="utf-8")
        # Validate JSON shape lightly before showing.
        parsed = json.loads(rubric_text)
        if not isinstance(parsed, list):
            return None, None, f"Refined rubric exists but is not a JSON list: {rubric_path}"
        final_change_summary = _read_json(rubric_path.with_name("change_summary.json"))
        return json.dumps(parsed, indent=2), final_change_summary, ""
    except (OSError, json.JSONDecodeError) as exc:
        return None, None, f"Could not read refined rubric JSON: {exc}"


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

        logs_placeholder = st.empty()
        summary_placeholder = st.empty()
        log_lines: list[str] = []

        def _on_output_line(line: str) -> None:
            log_lines.append(line)
            # Keep UI concise: show the latest chunk of logs.
            logs_placeholder.code("\n".join(log_lines[-120:]) or "Starting...")

        def _on_iteration_complete() -> None:
            summary = _get_latest_change_summary()
            if summary is not None:
                summary_placeholder.subheader("Change Summary (live)")
                summary_placeholder.json(summary)

        with st.spinner("Running rubric_opt_task pipeline... this can take a while."):
            rubric_json_text, final_change_summary, error = run_rubric_opt_task(
                prompt,
                dataset_bytes,
                int(iterations),
                on_output_line=_on_output_line,
                on_iteration_complete=_on_iteration_complete,
            )

        if error:
            st.error("rubric_opt_task failed.")
            st.code(error)
            return

        st.success("Optimized rubric generated.")
        st.subheader("Optimized rubric.json (raw)")
        st.code(rubric_json_text or "", language="json")
        if final_change_summary is not None:
            st.subheader("Final change_summary.json")
            st.json(final_change_summary)


if __name__ == "__main__":
    main()
