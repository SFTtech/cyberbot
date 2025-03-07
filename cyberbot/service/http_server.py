from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Awaitable, Callable

from aiohttp import web

from ..api.service import Service

if TYPE_CHECKING:
    from ..bot import Bot

logger = logging.getLogger(__name__)


type RequestHandler = Callable[[str, web.BaseRequest], Awaitable[web.StreamResponse | None]]


class HTTPServer(Service):
    def __init__(self, bot: Bot) -> None:
        super().__init__(bot)

        self._bind_address = ""
        self._bind_port = 0
        self._base_url = ""

        # recursive tree of {str -> dict | RequestHandler}
        self._routes: dict = dict()

    async def setup(self) -> None:
        config = self._bot.get_config("http_server")
        if not config:
            raise Exception("http_server: config section missing")

        self._bind_address = config["bind_address"]
        self._bind_port = int(config["bind_port"])
        base_url = config.get("base_url")
        if not base_url:
            raise ValueError("please set http_server.base_url to a valid url prefix")
        self._base_url = base_url.rstrip("/")

        await self.register_path("/", self._index_page)

    async def _index_page(self, subpath: str, req: web.BaseRequest) -> web.StreamResponse:
        return web.Response(text=f"{self._bot.botname} is running here!")

    async def start(self) -> None:
        # we have to use the low level server instead of web.Application
        # since web.Application can't delete routes at runtime
        server = web.Server(self._handle_request)
        runner = web.ServerRunner(server)
        await runner.setup()

        site = web.TCPSite(runner, self._bind_address, self._bind_port)
        await site.start()

        logger.info(f"serving on {self._base_url} {self._bind_address}:{self._bind_port}...")

    async def register_path(self, path: str,
                            handler: RequestHandler) -> None:
        """
        Returns if the path was registered successfully.
        """

        path = path.lstrip("/").rstrip("/")
        parts = path.split("/")
        lastpart = parts[-1]

        # insert new tree entry
        node = self._routes
        for idx, part in enumerate(parts[:-1]):
            if part not in node:
                newnode: dict = dict()
                node[part] = newnode
                node = newnode
            elif isinstance(node, dict):
                node = node[part]
            else:
                raise KeyError(f"path {path!r} would overwrite handler {'/'.join(parts[:idx])}")

        if lastpart in node:
            raise KeyError(f"path {path!r} already registered")

        node[lastpart] = handler

        logger.info(f"registered http server path /{path}")

    async def deregister_path(self, path: str) -> None:
        """
        returns True if the path was deregistered, else False.
        """

        path = path.lstrip("/").rstrip("/")
        parts = path.split("/")
        lastpart = parts[-1]

        node: dict = self._routes
        for part in parts[:-1]:
            node = node[part]

        del node[lastpart]

    async def _handle_request(self, request: web.BaseRequest) -> web.StreamResponse:
        path = request.path.lstrip("/").rstrip("/")
        parts = path.split("/")

        node: dict | RequestHandler = self._routes
        for idx, part in enumerate(parts):
            if isinstance(node, dict):
                node = node[part]
            else:
                raise Exception("inconsistent")

            if callable(node):
                subpath = "/".join(parts[idx+1:])
                handler: RequestHandler = node
                res: web.StreamResponse | None = await handler(subpath, request)
                if res is None:
                    return web.Response(status=200)
                return res

        return web.Response(status=404, text="not found")

    async def format_url(self, subpath: str) -> str:
        return f"{self._base_url}{subpath}"
