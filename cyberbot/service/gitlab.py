from __future__ import annotations

import hmac

from aiohttp import web

from ..types import Err, Ok, Result
from .base.git_hook_server import GitHookServer


class GitLabServer(GitHookServer):
    def __init__(self):
        super().__init__("gitlab")

    async def _check_request(self, request: web.BaseRequest, secret: str) -> Result[str, str]:

        # TODO once gitlab signs its webhooks, implement verification here.
        # https://gitlab.com/gitlab-org/gitlab/-/issues/19367

        token = request.headers.get("X-Gitlab-Token")
        if not token:
            return Err("token header not found")

        if not hmac.compare_digest(secret, token):
            return Err("token does not match")

        event = request.headers.get("X-Gitlab-Event")
        if not event:
            return Err("event type header not found")

        return Ok(event)
