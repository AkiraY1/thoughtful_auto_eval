"""Minimal cross-provider inference helpers for OpenAI and Anthropic."""

from __future__ import annotations
from typing import Optional, Sequence, List, Dict
from anthropic import Anthropic
from openai import OpenAI
import os
from dotenv import load_dotenv

SUPPORTED_MODELS = {
    "gpt-4.1-2025-04-14": "openai",
    "claude-opus-4-1": "anthropic",
    "claude-sonnet-4-6": "anthropic",
}


def _normalize_model_name(model: str) -> str:
    """Accept provider-prefixed model names and return bare model id."""
    if "/" in model:
        # Examples: anthropic/claude-opus-4-1, openai/gpt-4.1-2025-04-14
        return model.split("/", 1)[1]
    return model


def infer(
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 512,
    temperature: float = 0.7,
    top_p: float = 1.0,
    stop: Optional[Sequence[str]] = None,
    timeout: float = 60.0,
) -> str:
    """
    Run a single inference call against a supported model.

    Args:
        model: The model to use for inference.
        system_prompt: The system prompt to use for inference.
        user_prompt: The user prompt to use for inference.
        max_tokens: The maximum number of tokens to generate.
        temperature: The temperature to use for inference.
        top_p: The top p to use for inference.
        stop: The stop sequences to use for inference.
        timeout: The timeout to use for inference.

    Returns:
        The generated text.
    """

    load_dotenv()

    normalized_model = _normalize_model_name(model)
    provider = SUPPORTED_MODELS.get(normalized_model)

    stop_list = list(stop) if stop else None

    match provider:

        case "openai":

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
            response = client.chat.completions.create(
                model=normalized_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=stop_list,
                timeout=timeout,
            )
            return response.choices[0].message.content or ""
        
        case "anthropic":
            client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            messages = [{"role": "user", "content": user_prompt}]
            response = client.messages.create(
                model=normalized_model,
                system=system_prompt,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stop_sequences=stop_list,
                timeout=timeout,
            )
        
        case _:
            supported = ", ".join(sorted(SUPPORTED_MODELS))
            raise ValueError(
                f"Unsupported model '{model}' (normalized: '{normalized_model}'). "
                f"Supported models: {supported}"
            )

    text_chunks = [block.text for block in response.content if block.type == "text"]
    return "".join(text_chunks).strip()

if __name__ == "__main__":
    # Test inference

    print(infer("gpt-4.1-2025-04-14", system_prompt="You are a helpful assistant.", user_prompt="What is the capital of France?"))
    print(infer("claude-opus-4-1", system_prompt="You are a helpful assistant.", user_prompt="What is the capital of France?"))