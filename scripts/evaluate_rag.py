"""Run an explicit live acceptance evaluation against a dedicated eval tenant."""
import argparse
import json
import math
import os
from pathlib import Path
import statistics
import time

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[1] / "evals/staging.json")
    parser.add_argument("--seed", action="store_true", help="Write synthetic fixtures to a dedicated eval tenant")
    parser.add_argument("--max-p95-seconds", type=float, default=60)
    args = parser.parse_args()
    key = os.environ.get("RAG_EVAL_API_KEY")
    if not key:
        parser.error("Set RAG_EVAL_API_KEY to the dedicated eval tenant API key")
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    results, elapsed = [], []
    with httpx.Client(base_url=args.base_url.rstrip("/"), headers={"Authorization": f"Bearer {key}"}, timeout=190) as client:
        client.get("/api/ready").raise_for_status()
        if args.seed:
            for document in dataset["documents"]:
                client.post("/api/knowledge", json=document).raise_for_status()
        for case in dataset["cases"]:
            started = time.monotonic()
            response = client.post("/api/chat-rag", json={"question": case["question"], "top_k": 5})
            elapsed.append(time.monotonic() - started)
            if response.status_code != 200:
                results.append({"id": case["id"], "passed": False, "http_status": response.status_code})
                continue
            data = response.json()
            answer = data["answer"].lower()
            sources = {s.get("source_name") for s in data["sources"]}
            fallback = data["status"] == "insufficient_evidence"
            citation_ids = {c["source_id"] for c in data["citations"]}
            source_ids = {s["id"] for s in data["sources"]}
            checks = {
                "fallback_correct": fallback == case.get("fallback", False),
                "expected_facts": all(t.lower() in answer for t in case.get("contains", [])),
                "forbidden_absent": not any(t.lower() in answer for t in case.get("forbidden", [])),
                "expected_evidence": set(case.get("sources", [])).issubset(sources),
                "citations_valid": not citation_ids if fallback else bool(citation_ids) and citation_ids.issubset(source_ids),
            }
            results.append({"id": case["id"], "passed": all(checks.values()), "checks": checks})
    p95 = sorted(elapsed)[max(0, math.ceil(.95 * len(elapsed)) - 1)]
    passed = all(r["passed"] for r in results) and p95 <= args.max_p95_seconds
    print(json.dumps({"passed": passed, "cases": results, "p50_seconds": statistics.median(elapsed),
                      "p95_seconds": p95, "max_p95_seconds": args.max_p95_seconds}, indent=2))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
