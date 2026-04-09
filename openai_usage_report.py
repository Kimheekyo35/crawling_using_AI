from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from token_cal import calc_cost

API_BASE = "https://api.openai.com/v1"


def _parse_iso8601(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _resolve_time_range(args: argparse.Namespace) -> tuple[int, int]:
    if args.start:
        start = _parse_iso8601(args.start)
    else:
        start = datetime.now(timezone.utc) - timedelta(minutes=args.since_minutes)

    if args.end:
        end = _parse_iso8601(args.end)
    else:
        end = datetime.now(timezone.utc)

    if end <= start:
        raise ValueError("end time must be later than start time")

    return int(start.timestamp()), int(end.timestamp())


def _api_get(path: str, params: dict[str, Any], api_key: str) -> dict[str, Any]:
    query = urlencode(params, doseq=True)
    url = f"{API_BASE}{path}?{query}"
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OpenAI API request failed: {exc.code} {exc.reason}\n{body}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach OpenAI API: {exc.reason}") from exc


def _collect_bucket_results(payload: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            bucket_results = node.get("results")
            if isinstance(bucket_results, list) and all(isinstance(item, dict) for item in bucket_results):
                results.extend(bucket_results)
            data = node.get("data")
            if isinstance(data, list):
                for item in data:
                    walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return results


def _matches_filters(item: dict[str, Any], model: str | None, project_id: str | None) -> bool:
    item_model = str(item.get("model", item.get("model_name", "")) or "")
    item_project = str(item.get("project_id", "") or "")

    model_ok = True if not model else item_model == model
    project_ok = True if not project_id else item_project == project_id
    return model_ok and project_ok


def _sum_usage(items: list[dict[str, Any]], model: str | None, project_id: str | None) -> dict[str, int]:
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_input_tokens": 0,
        "num_model_requests": 0,
        "matched_items": 0,
    }

    for item in items:
        if not _matches_filters(item, model=model, project_id=project_id):
            continue
        totals["matched_items"] += 1
        totals["input_tokens"] += int(item.get("input_tokens", 0) or 0)
        totals["output_tokens"] += int(item.get("output_tokens", 0) or 0)
        totals["cached_input_tokens"] += int(
            item.get("input_cached_tokens", item.get("cached_input_tokens", 0)) or 0
        )
        totals["num_model_requests"] += int(
            item.get("num_model_requests", item.get("requests", 0)) or 0
        )

    return totals


def _extract_cost_value(item: dict[str, Any]) -> float:
    amount = item.get("amount")
    if isinstance(amount, dict):
        return float(amount.get("value", 0.0) or 0.0)
    return float(item.get("cost", 0.0) or 0.0)


def _sum_costs(items: list[dict[str, Any]], project_id: str | None) -> tuple[float, int]:
    total = 0.0
    matched_items = 0

    for item in items:
        item_project = str(item.get("project_id", "") or "")
        if project_id and item_project != project_id:
            continue
        matched_items += 1
        total += _extract_cost_value(item)

    return total, matched_items


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch recent OpenAI organization usage and costs."
    )
    parser.add_argument(
        "--since-minutes",
        type=int,
        default=60,
        help="Look back this many minutes if --start is not provided.",
    )
    parser.add_argument(
        "--start",
        help="UTC start time in ISO 8601, for example 2025-04-06T02:00:00Z",
    )
    parser.add_argument(
        "--end",
        help="UTC end time in ISO 8601, for example 2025-04-06T03:00:00Z",
    )
    parser.add_argument(
        "--model",
        default="gpt-5",
        help="Filter usage rows by exact model name. Use empty string to disable.",
    )
    parser.add_argument(
        "--project-id",
        help="Optional OpenAI project id filter.",
    )
    parser.add_argument(
        "--show-raw",
        action="store_true",
        help="Print raw JSON payloads for debugging.",
    )
    return parser


def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_ADMIN_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_ADMIN_API_KEY or OPENAI_API_KEY is required.")

    model_filter = args.model or None
    start_ts, end_ts = _resolve_time_range(args)

    usage_params: dict[str, Any] = {
        "start_time": start_ts,
        "end_time": end_ts,
        "group_by": ["model", "project_id"],
    }
    cost_params: dict[str, Any] = {
        "start_time": start_ts,
        "end_time": end_ts,
        "group_by": ["project_id", "line_item"],
    }

    try:
        usage_payload = _api_get("/organization/usage/completions", usage_params, api_key)
        cost_payload = _api_get("/organization/costs", cost_params, api_key)
    except RuntimeError as exc:
        message = str(exc)
        if "403" in message or "admin" in message.lower():
            message += (
                "\nThis endpoint usually requires an organization admin API key. "
                "Set OPENAI_ADMIN_API_KEY and try again."
            )
        raise SystemExit(message) from exc

    usage_items = _collect_bucket_results(usage_payload)
    cost_items = _collect_bucket_results(cost_payload)

    usage_totals = _sum_usage(usage_items, model=model_filter, project_id=args.project_id)
    estimated_cost = calc_cost(
        input_tokens=usage_totals["input_tokens"],
        output_tokens=usage_totals["output_tokens"],
        cached_input_tokens=usage_totals["cached_input_tokens"],
    )
    organization_cost, matched_cost_items = _sum_costs(cost_items, project_id=args.project_id)

    print(
        f"time_range_utc={datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat()} "
        f"to {datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat()}"
    )
    print(f"model_filter={model_filter or 'none'}")
    print(f"project_filter={args.project_id or 'none'}")
    print(f"usage_rows_matched={usage_totals['matched_items']}")
    print(f"cost_rows_matched={matched_cost_items}")
    print(f"input_tokens={usage_totals['input_tokens']}")
    print(f"cached_input_tokens={usage_totals['cached_input_tokens']}")
    print(f"output_tokens={usage_totals['output_tokens']}")
    print(f"num_model_requests={usage_totals['num_model_requests']}")
    print(f"estimated_model_cost_usd={estimated_cost:.6f}")
    print(f"organization_cost_usd={organization_cost:.6f}")

    if args.show_raw:
        print("--- usage payload ---")
        print(json.dumps(usage_payload, ensure_ascii=False, indent=2))
        print("--- cost payload ---")
        print(json.dumps(cost_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        sys.exit(str(exc))
