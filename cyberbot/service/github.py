from __future__ import annotations

import hmac
import hashlib
from typing import TYPE_CHECKING

from aiohttp import web

from .base.git_hook_server import GitHookServer
from ..types import Err, Ok, Result

if TYPE_CHECKING:
    from ..bot import Bot


def verify_signature(body: bytes, secret_token: str, signature_header: str) -> bool:
    """
    verify the github hmac signature with our shared secret.
    """

    hash_object = hmac.new(secret_token.encode('utf-8'), body, digestmod=hashlib.sha256)
    expected_signature = f"sha256={hash_object.hexdigest()}"
    if hmac.compare_digest(expected_signature, signature_header):
        return True
    return False


class GitHubServer(GitHookServer):
    def __init__(self, bot: Bot):
        super().__init__(bot, "github")

    async def _check_request(self, request: web.BaseRequest, secret: str) -> Result[str, str]:

        msgsig = request.headers.get("X-Hub-Signature-256")
        if not msgsig:
            raise ValueError("message doesn't have a signature.")

        body = await request.read()
        if not verify_signature(body, secret, msgsig):
            return Err("wrong signature")

        event = request.headers.get("X-GitHub-Event")
        if event is None:
            return Err("event header missing")

        return Ok(event)
