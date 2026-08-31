"""Compare semantic or hybrid retrieval with the frozen keyword baseline."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.evaluate import grade_case, load_cases, summarize
from src.embeddings import (
    DEFAULT_DIMENSIONS,
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingError,
    OpenAIEmbeddingService,
)
from src.retrieve import load_markdown_chunks
from src.semantic_retrieve import HybridRetriever


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["semantic", "hybrid"], default="hybrid")
    parser.add_argument("--budget-cny", type=float, default=1.0)
    parser.add_argument("--output-dir", type=Path, default=Path("eval/embedding-run"))
    args = parser.parse_args()

    load_dotenv()
    model = os.environ.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    dimensions = int(os.environ.get("EMBEDDING_DIMENSIONS", DEFAULT_DIMENSIONS))
    cases = load_cases(Path("eval/questions.jsonl"))
    chunks = load_markdown_chunks(Path("data/demo"))

    try:
        service = OpenAIEmbeddingService(
            model=model,
            dimensions=dimensions,
            budget_cny=args.budget_cny,
            cache_path=Path("data/cache/embeddings.json"),
        )
        setup_cost_before = service.usage.cost_usd
        retriever = HybridRetriever(chunks, service)
        setup_cost = service.usage.cost_usd - setup_cost_before

        results = []
        for index, case in enumerate(cases):
            before_cost = service.usage.cost_usd
            started = time.perf_counter()
            if args.mode == "semantic":
                search_results = retriever.search_semantic(case["query"], top_k=3)
            else:
                search_results = retriever.search_hybrid(case["query"], top_k=3)
            latency_ms = (time.perf_counter() - started) * 1000
            request_cost = service.usage.cost_usd - before_cost
            if index == 0:
                request_cost += setup_cost
            results.append(
                grade_case(
                    case,
                    search_results,
                    variant=f"{args.mode}-{model}-{dimensions}",
                    latency_ms=latency_ms,
                    cost_usd=request_cost,
                )
            )
    except EmbeddingError as exc:
        print(f"Embedding评测未运行：{exc}", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path = args.output_dir / f"{args.mode}-results.jsonl"
    summary_path = args.output_dir / f"{args.mode}-summary.json"
    results_path.write_text(
        "\n".join(json.dumps(asdict(result), ensure_ascii=False) for result in results)
        + "\n",
        encoding="utf-8",
    )
    summary = summarize(results)
    summary.update(
        {
            "mode": args.mode,
            "model": model,
            "dimensions": dimensions,
            "session_prompt_tokens": service.usage.prompt_tokens,
            "session_api_calls": service.usage.api_calls,
            "session_cache_hits": service.usage.cache_hits,
            "session_cost_cny": service.usage.cost_cny,
            "budget_cny": args.budget_cny,
        }
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

