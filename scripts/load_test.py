"""Simple load test: concurrent health + list requests against a running Linevora.

Usage: python scripts/load_test.py --url http://127.0.0.1:8000 --requests 100 --concurrency 10
Uses only the stdlib; reports p95 latency.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import statistics
import time
import urllib.request


def one(url: str) -> float:
    start = time.perf_counter()
    with urllib.request.urlopen(url + "/v1/health", timeout=10) as response:
        response.read()
    return (time.perf_counter() - start) * 1000


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    args = parser.parse_args()
    with concurrent.futures.ThreadPoolExecutor(args.concurrency) as pool:
        latencies = list(pool.map(lambda _i: one(args.url), range(args.requests)))
    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    print(
        f"requests={len(latencies)} mean={statistics.mean(latencies):.1f}ms "
        f"p95={p95:.1f}ms max={latencies[-1]:.1f}ms"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
