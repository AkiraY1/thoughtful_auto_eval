from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import streamlit as st


REPO_ROOT = Path(__file__).resolve().parent
TASK_DIR = REPO_ROOT / "src" / "harbor_rubric_task"
SYSTEM_PROMPT_REL_PATH = Path("environment/system_prompt.txt")
RUBRIC_CREATION_REL_PATH = Path("environment/skills/rubric_creation/SKILL.md")
JOBS_DIR = REPO_ROOT / "jobs"


def _list_rubric_artifacts() -> set[Path]:
    if not JOBS_DIR.exists():
        return set()
    return set(JOBS_DIR.glob("**/artifacts/rubric.txt"))


def run_rubric_task(system_prompt: str, rubric_creation_skill: str) -> tuple[str | None, str]:
    if not TASK_DIR.exists():
        return None, f"Missing task directory: {TASK_DIR}"

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None, "ANTHROPIC_API_KEY is not set in the environment."

    before = _list_rubric_artifacts()

    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_task_dir = Path(tmp_dir) / TASK_DIR.name
        shutil.copytree(TASK_DIR, temp_task_dir)

        temp_system_prompt_path = temp_task_dir / SYSTEM_PROMPT_REL_PATH
        temp_system_prompt_path.parent.mkdir(parents=True, exist_ok=True)
        temp_system_prompt_path.write_text(system_prompt, encoding="utf-8")

        temp_rubric_creation_path = temp_task_dir / RUBRIC_CREATION_REL_PATH
        temp_rubric_creation_path.parent.mkdir(parents=True, exist_ok=True)
        temp_rubric_creation_path.write_text(rubric_creation_skill, encoding="utf-8")

        completed = subprocess.run(
            [
                "harbor",
                "run",
                "-p",
                str(temp_task_dir),
                "--env",
                "modal",
                "--force-build",
                "--agent",
                "claude-code",
                "--model",
                "anthropic/claude-opus-4-1",
                "--ae",
                f"ANTHROPIC_API_KEY={os.environ['ANTHROPIC_API_KEY']}",
                "--artifact",
                "/app/rubric.txt",
                "--yes",
            ],
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
    st.set_page_config(page_title="Agentic Eval Creation", layout="wide")
    st.title("Agentic Eval Creation")
    st.write(
        "Enter a system prompt that you want your LLM to follow, and we will create a rubric that an LLM judge can use to evaluate how closely your model follows it. You can edit the rubric creation principles as well if you have any specific design criteria."
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

    rubric_creation_source = TASK_DIR / RUBRIC_CREATION_REL_PATH
    default_rubric_creation = ""
    if rubric_creation_source.exists():
        default_rubric_creation = rubric_creation_source.read_text(encoding="utf-8")

    if "rubric_creation_skill_text" not in st.session_state:
        st.session_state["rubric_creation_skill_text"] = default_rubric_creation

    rubric_creation_skill = st.text_area(
        "Principles to build a good LLM judge rubric",
        key="rubric_creation_skill_text",
        height=180,
    )

    run_clicked = st.button("Run rubric_task", type="primary", use_container_width=True)

    if run_clicked:
        prompt = system_prompt.strip()
        if not prompt:
            st.error("Please provide a non-empty system prompt.")
            return

        with st.spinner("Running rubric_task... this can take a while."):
            rubric_text, error = run_rubric_task(prompt, rubric_creation_skill)

        if error:
            st.error("rubric_task failed.")
            st.code(error)
            return

        st.success("Rubric generated.")
        st.subheader("Generated rubric.txt")
        st.text_area("Rubric", value=rubric_text or "", height=350)


if __name__ == "__main__":
    main()
