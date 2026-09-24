"""Send one prompt to a local Ollama model and inspect its metrics."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any

import requests

OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen3.5:2b"
DEFAULT_MAX_OUTPUT_TOKENS = 256


@dataclass(frozen=True)
class GenerationResult:
    """Normalized text and operational metrics from one Ollama response."""

    model: str
    text: str
    total_seconds: float
    load_seconds: float
    prompt_tokens: int
    output_tokens: int
    output_tokens_per_second: float


def nanoseconds_to_seconds(value: float | None) -> float:
    """Convert an Ollama duration field to seconds."""
    return float(value or 0) / 1_000_000_000


def parse_generation(data: dict[str, Any]) -> GenerationResult:
    """Validate and normalize the fields used by this lesson."""
    generated_text = data.get("response")
    if not isinstance(generated_text, str):
        raise TypeError("Expected Ollama's 'response' field to contain text")

    eval_seconds = nanoseconds_to_seconds(data.get("eval_duration"))
    output_tokens = int(data.get("eval_count", 0))
    throughput = output_tokens / eval_seconds if eval_seconds > 0 else 0.0

    return GenerationResult(
        model=str(data.get("model", "unknown")),
        text=generated_text,
        total_seconds=nanoseconds_to_seconds(data.get("total_duration")),
        load_seconds=nanoseconds_to_seconds(data.get("load_duration")),
        prompt_tokens=int(data.get("prompt_eval_count", 0)),
        output_tokens=output_tokens,
        output_tokens_per_second=throughput,
    )


def query_ollama(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    timeout: float = 120,
) -> GenerationResult:
    """Generate one complete response through Ollama's local HTTP API."""
    if max_output_tokens < 1:
        raise ValueError("max_output_tokens must be at least 1")

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_output_tokens,
        },
    }
    response = requests.post(
        OLLAMA_GENERATE_URL,
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    response_data = response.json()
    if not isinstance(response_data, dict):
        raise TypeError("Expected Ollama to return a JSON object")
    return parse_generation(response_data)


def build_parser() -> argparse.ArgumentParser:
    """Define the command-line options used in the exercise."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "prompt",
        nargs="?",
        default="Explain one product risk of using a local LLM.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
    )
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    """Run the client and print either a readable or JSON result."""
    args = build_parser().parse_args()
    print(f"Querying {args.model} through Ollama...", file=sys.stderr, flush=True)

    try:
        result = query_ollama(
            args.prompt,
            model=args.model,
            temperature=args.temperature,
            max_output_tokens=args.max_output_tokens,
            timeout=args.timeout,
        )
    except requests.Timeout as exc:
        print(
            "Ollama did not return a complete response before the timeout. "
            "Confirm that the model is running, then try a shorter prompt or "
            "a smaller --max-output-tokens value.\n"
            f"{exc}"
        )
        return 1
    except requests.RequestException as exc:
        print(
            "Could not reach Ollama. Start the application or local service, "
            f"confirm that {args.model!r} is installed, and try again.\n{exc}"
        )
        return 1
    except (TypeError, ValueError, KeyError) as exc:
        print(f"Ollama returned an unexpected response: {exc}")
        return 1

    if args.as_json:
        print(json.dumps(asdict(result), indent=2, ensure_ascii=True))
        return 0

    print(result.text)
    print("\n--- Ollama metrics ---")
    print(f"Model: {result.model}")
    print(f"Total duration: {result.total_seconds:.2f} s")
    print(f"Load duration: {result.load_seconds:.2f} s")
    print(f"Prompt tokens: {result.prompt_tokens}")
    print(f"Output tokens: {result.output_tokens}")
    print(f"Generation throughput: {result.output_tokens_per_second:.2f} tok/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
