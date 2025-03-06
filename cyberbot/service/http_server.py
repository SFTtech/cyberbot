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
        self._paths: dict[str, RequestHandler] = {}

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

    async def register_path(self, path_prefix: str, handler: RequestHandler) -> bool:
        """
        Returns if the path was registered successfully.
        """

        path_prefix = path_prefix.lstrip("/").rstrip("/")
        if "/" in path_prefix:
            # we just support top-level routing for now.
            raise ValueError("no middle / allowed in http server path registration for subpaths")

        logger.info(f"Registering http server path /{path_prefix}")

        if path_prefix in self._paths:
            return False

        self._paths[path_prefix] = handler
        return True

    async def deregister_path(self, path: str) -> bool:
        """
        returns True if the path was deregistered, else False.
        """
        if path not in self._paths:
            return False
        del self._paths[path]
        return True

    async def _handle_request(self, request: web.BaseRequest) -> web.StreamResponse:
        path_parts = request.path.split("/", maxsplit=2)
        prefix_path = path_parts[1]

        if handler := self._paths.get(prefix_path):
            subpath = path_parts[2] if len(path_parts) >= 3 else ""
            res: web.StreamResponse | None = await handler(subpath, request)
            if res is None:
                return web.Response(status=200)
            return res

        else:
            return web.Response(status=404, text=f"path {prefix_path!r} not found")

    async def get_url(self):
        return self._base_url
