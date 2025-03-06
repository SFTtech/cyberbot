from __future__ import annotations

import asyncio
import logging
import textwrap
import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass

from aiohttp import web

from ...api.service import Service
from ...service.http_server import HTTPServer
from ...types import Err, Ok, Result

if typing.TYPE_CHECKING:
    from typing import Any

    from ...bot import Bot


logger = logging.getLogger(__name__)


class BaseGitHookHandler(ABC):
    @abstractmethod
    async def handle_git_hook(self, subpath: str, event: str, content: Any) -> None:
        pass


@dataclass
class _GitHookHandle:
    secret: str
    handler: BaseGitHookHandler


class GitHookServer(Service):
    def __init__(self, bot: Bot, git_variant: str):
        super().__init__(bot)

        # {hook subpath -> _GitHookHandler}
        self._handles: dict[str, _GitHookHandle] = dict()
        self._http_server: HTTPServer | None = None

        self._git_variant = git_variant
        self._path: str = ""

        self._base_url: str = ""

    @abstractmethod
    async def _check_request(self, request: web.BaseRequest, secret: str) -> Result[str, str]:
        """
        validate the webhook signature.
        parse requests is used to extract the webhook's "event" (push, ...).
        return OK[event] or Err[msg]
        """
        pass

    async def setup(self):
        self._http_server = typing.cast(
            HTTPServer,
            self._bot.get_service("http_server")
        )

        config = self._bot.get_config(f"{self._git_variant}_server")
        if config is None:
            raise ValueError(f"[{self._git_variant}_server] not found in config")

        path = config["webhook_path"]

        # ensure single surrounding /path/
        self._path = f"/{path.lstrip('/').rstrip('/')}/"

    async def format_url(self, subpath: str) -> str:
        """
        return hook server url for a subpath.
        _base_url ends in /
        """
        if self._http_server is None:
            raise Exception("http server not yet set up")

        return f"{await self._http_server.get_url()}{self._path}{subpath}"

    async def start(self):
        if not self._http_server:
            raise Exception("http server is not setup yet")

        res = await self._http_server.register_path(self._path, self._handle_request)
        if res is None:
            raise Exception(f"Failed registering {self._git_variant}_server webhook_path {self._path} to http_server")

    def register_hook(self, webhook_subpath: str, secret: str, handler: BaseGitHookHandler) -> None:
        """
        handler has to be a async function and has to have a method
        called 'handle(token, event, content)' where event is
        the git event and content ist the parsed json from the webhook post
        """

        self._handles[webhook_subpath] = _GitHookHandle(
            secret=secret,
            handler=handler,
        )

    async def deregister_hook(self, webhook_subpath: str):
        del self._handles[webhook_subpath]

    async def _handle_request(self, subpath: str, request: web.BaseRequest) -> web.StreamResponse:
        match request.method:
            case "GET":
                text = textwrap.dedent(f"""\
                <html>
                    <head>
                        <title>Ooooooooooops</title>
                    </head>
                    <body>
                    <p>
                        Please don't open the url in your browser, but
                        rather paste the url and the token into your
                        instance of {self._git_variant}'s webhook settings under
                        Settings/Webhooks.
                    </p>
                    </body>
                </html>
                """)
                return web.Response(text=text, content_type="text/html")

            case "POST":
                pass
            case _:
                return web.Response(text="unsupported method", status=404)

        handle = self._handles.get(subpath)

        if not handle:
            return web.Response(text=f"git hook subpath handler {subpath!r} not found", status=404)

        # check msg signature
        match await self._check_request(request, handle.secret):
            case Err(msg):
                return web.Response(text=msg, status=400)
            case Ok(_event):
                event = _event

        try:
            content = await request.json()
        except web.HTTPBadRequest as exc:
            return web.Response(text=f"failed to decode content json: {exc.reason}", status=400)

        try:
            async with asyncio.timeout(2):
                await handle.handler.handle_git_hook(subpath=subpath, event=event, content=content)
        except TimeoutError:
            return web.Response(text="timeout", status=501)

        return web.Response(status=200)
