from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
import dotenv
import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

dotenv.load_dotenv()

from app.tracing import get_langfuse_client


def print_status(client) -> None:
    print("--- Current Prompt Status on Langfuse ---")
    for v in [1, 2]:
        try:
            p = client.get_prompt("day13-chat", version=v)
            print(f"Version {v}: labels={p.labels}, prompt={repr(p.prompt[:50])}...")
        except Exception as e:
            print(f"Version {v}: error {e}")


def promote_v2(client) -> None:
    print("Promoting version 2 to 'production'...")
    client.update_prompt(name="day13-chat", version=2, new_labels=["candidate", "production"])
    client.clear_prompt_cache()
    print("Promotion completed! Current labels on v2:")
    p = client.get_prompt("day13-chat", version=2)
    print(f"Version 2 labels: {p.labels}")


def rollback_v1(client) -> None:
    print("Rolling back 'production' to version 1...")
    client.update_prompt(name="day13-chat", version=1, new_labels=["baseline", "production"])
    client.clear_prompt_cache()
    print("Rollback completed! Current labels on v1:")
    p = client.get_prompt("day13-chat", version=1)
    print(f"Version 1 labels: {p.labels}")


def run_request(label: str, message: str = "Explain why observability needs metrics, logs, and traces") -> None:
    url = "http://127.0.0.1:8000/chat"
    payload = {
        "user_id": "u_eval_01",
        "session_id": f"s_eval_{label}",
        "feature": "qa",
        "message": message,
    }
    with httpx.Client(timeout=30.0) as http_client:
        start = time.perf_counter()
        resp = http_client.post(url, json=payload)
        latency = (time.perf_counter() - start) * 1000
        data = resp.json()
        print(f"[{label.upper()}] HTTP {resp.status_code} | correlation_id: {data.get('correlation_id')} | latency: {latency:.1f}ms")


def main() -> None:
    client = get_langfuse_client()
    parser = argparse.ArgumentParser(description="Manage Langfuse prompt versioning workflow")
    parser.add_argument("action", choices=["status", "promote", "rollback", "demo-cycle"], help="Action to perform")
    args = parser.parse_args()

    if args.action == "status":
        print_status(client)
    elif args.action == "promote":
        promote_v2(client)
    elif args.action == "rollback":
        rollback_v1(client)
    elif args.action == "demo-cycle":
        print_status(client)
        print("\n1. Sending request with baseline (v1)...")
        rollback_v1(client)
        run_request("baseline_v1")
        time.sleep(1)

        print("\n2. Promoting candidate (v2) to production...")
        promote_v2(client)
        run_request("candidate_v2")
        time.sleep(1)

        print("\n3. Rolling back production to v1...")
        rollback_v1(client)
        run_request("rollback_v1")
        print("\nDemo cycle completed!")


if __name__ == "__main__":
    main()
