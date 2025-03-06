#!/usr/bin/env python3

import argparse
import asyncio
import json
import hmac
import hashlib

from typing import Any

import aiohttp


async def send_webhook(target_url: str, hooksecret: str, event_type, payload: Any):
    payload_raw = json.dumps(payload).encode()

    signature = 'sha256=' + hmac.new(hooksecret.encode(), payload_raw, hashlib.sha256).hexdigest()
    headers = {"X-Hub-Signature-256": signature,
               "X-GitHub-Event": event_type}

    print(f"submitting pullreq webhook to {target_url!r}...")
    async with aiohttp.ClientSession() as session:
        async with session.post(target_url,
                                data=payload_raw, headers=headers) as resp:
            print(f"hook answer {'ok' if resp.ok else 'bad'} ({resp.status}): {await resp.text()!r}")


def get_payload(event_type: str) -> Any:

    sender = {"name": "Hans Dampf", "username": "pr0dampf0r",
              "html_url": "http://user-link", "avatar_url": "http://user-avatar"}

    match event_type:
        case "push":
            return {
                "sender": sender,
                "ref": "refs/heads/lol-pullrequest",
                "ref_type": "branch",
                "compare": "http://compare-stuff/a..b",
                "commits": [{"id": "commitid", "message": "msg", "timestamp": "timestamp",
                             "author": sender,
                             "url": "http://commit-url"}],
                "repository": {"name": "repo/name", "html_url": "http://repo-url",
                               "description": "desc", "id": "repoid"},
            }
        case _:
            raise NotImplementedError()


def main():
    """
    entry point
    """
    cli = argparse.ArgumentParser(description='send github webhooks for testing reasons')
    cli.add_argument("hook_url")
    cli.add_argument("secret")
    cli.add_argument("event_type", choices=["push"])
    args = cli.parse_args()

    payload = get_payload(args.event_type)

    asyncio.run(send_webhook(args.hook_url, args.secret, args.event_type, payload))


if __name__ == "__main__":
    main()
