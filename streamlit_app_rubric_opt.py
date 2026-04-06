from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

import streamlit as st


REPO_ROOT = Path(__file__).resolve().parent
RUN_SCRIPT = REPO_ROOT / "harbor_scripts" / "run_rubric_opt_task.sh"
JOBS_DIR = REPO_ROOT / "jobs"
STABLE_REFINE_DIR = JOBS_DIR / "latest_harbor_rubric_refine_artifacts"
RUBRIC_CREATION_SKILL_PATH = (
    REPO_ROOT
    / "src"
    / "harbor_rubric_opt_task"
    / "environment"
    / "skills"
    / "rubric_creation"
    / "SKILL.md"
)
RUBRIC_REFINEMENT_SKILL_PATH = (
    REPO_ROOT
    / "src"
    / "harbor_rubric_refine_task"
    / "environment"
    / "skills"
    / "rubric_refinement"
    / "SKILL.md"
)


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


def _get_latest_optimization_loop_dir() -> Path | None:
    if not JOBS_DIR.exists():
        return None
    candidates = list(
        JOBS_DIR.glob("**/harbor_rubric_opt_task__*/artifacts/optimization_loop")
    )
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _read_json_pretty(path: Path) -> str | None:
    data = _read_json(path)
    if data is None:
        return None
    return json.dumps(data, indent=2)


def run_rubric_opt_task(
    system_prompt: str,
    dataset_bytes: bytes,
    iterations: int,
    selected_model: str,
    rubric_creation_skill_text: str | None = None,
    rubric_refinement_skill_text: str | None = None,
    on_output_line: Callable[[str], None] | None = None,
    on_iteration_complete: Callable[[], None] | None = None,
) -> tuple[str | None, Any | None, str]:
    if not RUN_SCRIPT.exists():
        return None, None, f"Missing run script: {RUN_SCRIPT}"

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None, None, "ANTHROPIC_API_KEY is not set in the environment."

    before = _list_final_optimized_rubrics()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        prompt_path = tmp / "systemPrompt.txt"
        dataset_path = tmp / "responses.json"
        rubric_creation_skill_path = tmp / "rubric_creation_skill.md"
        rubric_refinement_skill_path = tmp / "rubric_refinement_skill.md"

        prompt_path.write_text(system_prompt, encoding="utf-8")
        dataset_path.write_bytes(dataset_bytes)

        cmd = [str(RUN_SCRIPT), str(prompt_path), str(dataset_path), str(iterations)]
        if rubric_creation_skill_text is not None and rubric_refinement_skill_text is not None:
            rubric_creation_skill_path.write_text(
                rubric_creation_skill_text, encoding="utf-8"
            )
            rubric_refinement_skill_path.write_text(
                rubric_refinement_skill_text, encoding="utf-8"
            )
            cmd.extend(
                [str(rubric_creation_skill_path), str(rubric_refinement_skill_path)]
            )
        process = subprocess.Popen(
            cmd,
            cwd=REPO_ROOT,
            env={
                **os.environ,
                "RUBRIC_OPT_MODEL": selected_model,
                "RUBRIC_REFINE_MODEL": selected_model,
            },
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
    st.title("Rubric Optimization")
    st.write(
        "Provide a system prompt and upload a JSON dataset. The pipeline iteratively runs rubric creation and refinement, then returns an optimized rubric."
    )

    left_col, right_col = st.columns([1, 1], gap="large")

    with left_col:
        if "rubric_creation_skill_text" not in st.session_state:
            st.session_state["rubric_creation_skill_text"] = (
                RUBRIC_CREATION_SKILL_PATH.read_text(encoding="utf-8")
                if RUBRIC_CREATION_SKILL_PATH.exists()
                else ""
            )
        if "rubric_refinement_skill_text" not in st.session_state:
            st.session_state["rubric_refinement_skill_text"] = (
                RUBRIC_REFINEMENT_SKILL_PATH.read_text(encoding="utf-8")
                if RUBRIC_REFINEMENT_SKILL_PATH.exists()
                else ""
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
            "Upload data to test rubric on...", type=["json"]
        )
        iterations = st.number_input(
            "Optimization iterations",
            min_value=1,
            max_value=20,
            value=2,
            step=1,
            help="Number of judge->refine loop iterations to run.",
        )
        selected_model_label = st.selectbox(
            "Model",
            options=["Claude Sonnet 4.6", "Claude Opus 4.1"],
            index=0,
        )
        selected_model = (
            "anthropic/claude-sonnet-4-6"
            if selected_model_label == "Claude Sonnet 4.6"
            else "anthropic/claude-opus-4-1"
        )

        with st.expander("Advanced Options", expanded=False):
            st.markdown("**Rubric creation and refinement skill overrides**")
            st.text_area(
                "Rubric Creation",
                key="rubric_creation_skill_text",
                height=220,
            )
            st.text_area(
                "Rubric Refinement",
                key="rubric_refinement_skill_text",
                height=220,
            )

        run_clicked = st.button(
            "Run rubric optimization", type="primary", use_container_width=True
        )

    with right_col:
        progress_placeholder = st.empty()
        progress_bar_placeholder = st.empty()
        eta_placeholder = st.empty()
        timings_placeholder = st.empty()
        change_summary_placeholder = st.empty()
        rubric_versions_placeholder = st.empty()
        final_rubric_placeholder = st.empty()

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

        log_lines: list[str] = []
        completed_iterations = 0
        rubric_panel_refresh_count = 0
        start_ts = time.time()
        progress_placeholder.info("Run started. Waiting for iteration updates...")
        progress_bar = progress_bar_placeholder.progress(0.0)
        eta_placeholder.caption(
            f"Estimated time remaining: {int(iterations) * 6} min (assumes 6 min/iteration)"
        )

        def _update_progress_display() -> None:
            nonlocal completed_iterations
            total = max(int(iterations), 1)
            ratio = min(max(completed_iterations / total, 0.0), 1.0)
            progress_bar.progress(ratio)

            elapsed_sec = max(time.time() - start_ts, 0.0)
            remaining_iters = max(total - completed_iterations, 0)
            est_remaining_sec = remaining_iters * 6 * 60
            est_total_sec = total * 6 * 60
            eta_placeholder.caption(
                "Iterations completed: "
                f"{completed_iterations}/{total} | "
                f"Elapsed: {int(elapsed_sec // 60)}m {int(elapsed_sec % 60)}s | "
                f"Est. remaining: {int(est_remaining_sec // 60)}m {int(est_remaining_sec % 60)}s "
                f"(assumed total: {int(est_total_sec // 60)} min)"
            )

        def _refresh_right_panel() -> None:
            nonlocal rubric_panel_refresh_count
            rubric_panel_refresh_count += 1
            change_summary = _get_latest_change_summary()
            if change_summary is not None:
                with change_summary_placeholder.container():
                    st.markdown("**Change Summary (live)**")
                    st.json(change_summary)

            loop_dir = _get_latest_optimization_loop_dir()
            if loop_dir is None:
                return

            iter_dirs = sorted(
                [p for p in loop_dir.glob("iter_*") if p.is_dir()],
                key=lambda p: p.name,
            )

            with timings_placeholder.container():
                st.markdown("**Iteration Timing Breakdown**")
                timing_lines: list[str] = []
                for iter_dir in iter_dirs:
                    timing_path = iter_dir / "timings.json"
                    timing = _read_json(timing_path)
                    if not isinstance(timing, dict):
                        timing_lines.append(f"- `{iter_dir.name}`: timing not available yet")
                        continue
                    judging = timing.get("judging_duration_sec", 0)
                    refinement = timing.get("refinement_duration_sec", 0)
                    total = timing.get("iteration_duration_sec", 0)
                    timing_lines.append(
                        f"- `{iter_dir.name}`: judging `{judging}s`, refinement `{refinement}s`, total `{total}s`"
                    )
                if timing_lines:
                    st.markdown("\n".join(timing_lines))
                else:
                    st.caption("No timing data yet.")

            with rubric_versions_placeholder.container():
                st.markdown("**Rubric Versions by Iteration**")
                for iter_dir in iter_dirs:
                    before_path = iter_dir / "rubric_before_refine.json"

                    st.markdown(f"`{iter_dir.name}`")
                    before_text = _read_json_pretty(before_path)
                    if before_text is not None:
                        st.text_area(
                            label=f"{iter_dir.name} rubric",
                            value=before_text,
                            height=140,
                            key=f"before_refine_{iter_dir.name}_{rubric_panel_refresh_count}",
                            disabled=True,
                            label_visibility="collapsed",
                        )
                    else:
                        st.caption("Not available yet.")

        def _on_output_line(line: str) -> None:
            log_lines.append(line)

        def _on_iteration_complete() -> None:
            nonlocal completed_iterations
            completed_iterations += 1
            _update_progress_display()
            progress_placeholder.info("Iteration completed. Updating right panel...")
            _refresh_right_panel()

        with st.spinner("Running rubric_opt_task pipeline... this can take a while."):
            rubric_json_text, final_change_summary, error = run_rubric_opt_task(
                prompt,
                dataset_bytes,
                int(iterations),
                selected_model,
                st.session_state["rubric_creation_skill_text"],
                st.session_state["rubric_refinement_skill_text"],
                on_output_line=_on_output_line,
                on_iteration_complete=_on_iteration_complete,
            )

        if error:
            st.error("rubric_opt_task failed.")
            st.code(error)
            return

        progress_placeholder.success("Optimization run complete.")
        completed_iterations = int(iterations)
        _update_progress_display()
        _refresh_right_panel()

        if final_change_summary is not None:
            with change_summary_placeholder.container():
                st.markdown("**Final change_summary.json**")
                st.json(final_change_summary)

        with final_rubric_placeholder.container():
            st.markdown("**Final optimized rubric.json (raw)**")
            st.code(rubric_json_text or "", language="json")


if __name__ == "__main__":
    main()
