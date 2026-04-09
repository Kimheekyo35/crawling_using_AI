from __future__ import annotations

import argparse

GPT5_INPUT_PER_MILLION = 0.75
GPT5_CACHED_INPUT_PER_MILLION = 0.08
GPT5_OUTPUT_PER_MILLION = 4.50


def calc_cost(input_tokens: int, output_tokens: int, cached_input_tokens: int = 0) -> float:
    billable_input_tokens = max(input_tokens - cached_input_tokens, 0)
    input_cost = (billable_input_tokens / 1_000_000) * GPT5_INPUT_PER_MILLION
    cached_input_cost = (cached_input_tokens / 1_000_000) * GPT5_CACHED_INPUT_PER_MILLION
    output_cost = (output_tokens / 1_000_000) * GPT5_OUTPUT_PER_MILLION
    return input_cost + cached_input_cost + output_cost


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Estimate OpenAI GPT-5 API cost from token usage."
    )
    parser.add_argument("--input", type=int, required=True, help="Total input tokens")
    parser.add_argument("--output", type=int, required=True, help="Total output tokens")
    parser.add_argument(
        "--cached-input",
        type=int,
        default=0,
        help="Cached input tokens included in the input total",
    )
    args = parser.parse_args()

    total = calc_cost(
        input_tokens=args.input,
        output_tokens=args.output,
        cached_input_tokens=args.cached_input,
    )
    print(f"estimated_cost_usd={total:.6f}")


if __name__ == "__main__":
    main()
