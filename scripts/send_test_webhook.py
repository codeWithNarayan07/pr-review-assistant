"""Send a correctly signed fake `pull_request` webhook to a locally running bot.

Example:  python scripts/send_test_webhook.py
          python scripts/send_test_webhook.py --action synchronize --sha 0123abc...
Only uses the Python standard library.
"""

import argparse
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
import uuid

DEMO_SHA = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"


def _secret_from_env_file() -> str | None:
    try:
        with open(".env") as fh:
            for line in fh:
                if line.startswith("GITHUB_WEBHOOK_SECRET="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", default="http://localhost:8000/webhook/github")
    p.add_argument(
        "--secret",
        default=os.environ.get("GITHUB_WEBHOOK_SECRET") or _secret_from_env_file() or "demo-secret",
    )
    p.add_argument(
        "--repo", 
        default="codeWithNarayan07/pr-review-assistant-test"
    )
    p.add_argument("--pr", type=int, default=1)
    p.add_argument("--sha", default=DEMO_SHA)
    p.add_argument("--action", default="opened")
    p.add_argument("--event", default="pull_request")
    args = p.parse_args()

    payload = {
        "action": args.action,
        "pull_request": {"number": args.pr, "draft": False, "head": {"sha": args.sha}},
        "repository": {"full_name": args.repo},
    }
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(args.secret.encode(), body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        args.url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": args.event,
            "X-GitHub-Delivery": str(uuid.uuid4()),
            "X-Hub-Signature-256": signature,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(resp.status, resp.read().decode())
    except urllib.error.HTTPError as exc:
        print(exc.code, exc.read().decode())
    except urllib.error.URLError as exc:
        print("Could not reach the bot:", exc.reason)


if __name__ == "__main__":
    main()
