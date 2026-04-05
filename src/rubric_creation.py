"""Generate evaluation rubrics from a target system prompt."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from llm_api import infer

DEFAULT_MODEL = "gpt-4.1-2025-04-14"
SYSTEM_PROMPT_FILENAME = "systemPrompt.txt"
JUDGE_RUBRIC_FILENAME = "judge_rubric.txt"

RUBRIC_GENERATOR_SYSTEM_PROMPT = """
You are an expert evaluator designer. Your task is to convert a target system prompt
into a strict, practical grading rubric for judging whether another LLM follows that
target system prompt.

Your output must be self-contained and directly usable by an LLM judge.
Focus on observable behaviors in model responses (not hidden reasoning).
""".strip()


def _build_rubric_request(target_system_prompt: str) -> str:
    """Build the user prompt sent to the rubric-generation LLM."""
    return f"""
Create a detailed rubric to evaluate whether an assistant reproduces the behaviors
required by the following target system prompt.

TARGET SYSTEM PROMPT:
---
{target_system_prompt}
---

Return ONLY the rubric in markdown with these sections:
1) ## Evaluation Goal
2) ## Scoring Scale (0-5)
   - Define what each score from 0 to 5 means globally.
3) ## Criteria
   - Provide 6-10 criteria.
   - For each criterion include:
     - name
     - weight (integer percentage; total weights must sum to 100)
     - what to check
     - failure modes
     - examples of high-score vs low-score behaviors
4) ## Pass/Fail Rule
   - Define minimum overall score and any critical-fail conditions.
5) ## Judge Instructions
   - Step-by-step instructions for an LLM judge on how to apply this rubric.
6) ## Output Format For The Judge
   - Provide a strict JSON schema the judge should output.

Requirements:
- Prioritize concrete and testable criteria.
- Penalize hallucination, instruction drift, and policy/style violations relevant to the target prompt.
- Keep the rubric provider-agnostic and model-agnostic.
- Do not include any text before or after the rubric.
""".strip()


def generate_rubric(
    target_system_prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1800,
    temperature: float = 0.1,
) -> str:
    """
    Generate a rubric for evaluating how well an LLM follows a target system prompt.

    Args:
        target_system_prompt: The original system prompt whose behaviors should be evaluated.
        model: The model used to create the rubric.
        max_tokens: Maximum tokens for rubric generation.
        temperature: Sampling temperature; lower values improve rubric consistency.

    Returns:
        A markdown rubric string.
    """
    if not target_system_prompt or not target_system_prompt.strip():
        raise ValueError("target_system_prompt must be a non-empty string.")

    rubric = infer(
        model=model,
        system_prompt=RUBRIC_GENERATOR_SYSTEM_PROMPT,
        user_prompt=_build_rubric_request(target_system_prompt.strip()),
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return rubric.strip()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an LLM-judge rubric from a target system prompt."
    )
    parser.add_argument(
        "--eval_dir",
        type=str,
        help="Path to an eval task directory containing systemPrompt.txt.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Model for rubric generation (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1800,
        help="Maximum tokens for rubric generation.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Sampling temperature for rubric generation.",
    )
    return parser.parse_args()


def _read_system_prompt_from_file(path_str: str) -> str:
    """Read target system prompt text from a file path."""
    path = Path(path_str).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"System prompt file not found: {path}")
    if path.suffix.lower() != ".txt":
        raise ValueError(f"System prompt file must be a .txt file: {path}")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"System prompt file is empty: {path}")
    return text


def _resolve_eval_paths(eval_dir_str: str) -> tuple[Path, Path, Path]:
    """
    Resolve and validate eval directory and standard input/output file paths.

    Returns:
        Tuple of (eval_dir, system_prompt_path, judge_rubric_path).
    """
    eval_dir = Path(eval_dir_str).expanduser()
    if not eval_dir.exists() or not eval_dir.is_dir():
        raise NotADirectoryError(f"Eval directory not found: {eval_dir}")

    system_prompt_path = eval_dir / SYSTEM_PROMPT_FILENAME
    if not system_prompt_path.exists():
        raise FileNotFoundError(
            f"Expected system prompt file not found: {system_prompt_path}"
        )

    judge_rubric_path = eval_dir / JUDGE_RUBRIC_FILENAME
    return eval_dir, system_prompt_path, judge_rubric_path


def main() -> None:
    args = _parse_args()
    _, system_prompt_path, judge_rubric_path = _resolve_eval_paths(args.eval_dir)
    target_prompt: Optional[str] = _read_system_prompt_from_file(str(system_prompt_path))

    rubric = generate_rubric(
        target_system_prompt=target_prompt,
        model=args.model,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )
    judge_rubric_path.write_text(f"{rubric}\n", encoding="utf-8")
    print(rubric)


if __name__ == "__main__":
    main()
