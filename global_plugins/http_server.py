import logging
import sys
import configparser
from aiohttp import web

logger = logging.getLogger(__name__)

class BotHTTPServer:

    def __init__(self):
        self.bind_address = ""
        self.bind_port = 0
        self.url = ""
        self.registered_paths = {}
        self.bot = None

    async def set_bot(self, bot):
        self.bot = bot
        if "http_server" not in self.bot.config:
            logger.error("invite_manager: invalid config file section")
            sys.exit(-1)
        self.config = self.bot.config["http_server"]
        self.bind_address = self.config.get("BIND_ADDRESS", "localhost")
        self.bind_port = int(self.config.get("BIND_PORT", "8080"))
        self.url = self.config.get("URL", "No URL configured in http_server")

    async def start(self):
        self.server = web.Server(self.handle_request)
        self.runner = web.ServerRunner(self.server)
        await self.runner.setup()

        self.site = web.TCPSite(self.runner, self.bind_address, self.bind_port)
        await self.site.start()
        logger.info(f"serving on {self.url} {self.bind_address}:{self.bind_port}")

    async def register_path(self, path, handler):
        """Returns the registered path e.g. for localhost/hallo/ -> hallo. None if path already has been registered."""
        logger.info(f"Registering path {path}")
        path = path.replace("/", "")
        if path in self.registered_paths or len(path) == 0:
            return None
        self.registered_paths[path] = handler
        return path

    async def deregister_path(self, path):
        """Returns the deregistered path e.g. for localhost/hallo/ -> hallo. None if path had not been registered."""
        path = path.replace("/", "")
        if path not in self.registered_paths or len(path) == 0:
            return None
        del self.registered_paths[path]
        return path

    async def handle_request(self, request):
        paths_parts = request.path.split('/')
    
        part = paths_parts[1]

        if part not in self.registered_paths:
            return web.Response(status=302, headers={"Location": "/index.html"})
        else:
            res = await (self.registered_paths[part](request))
            if res is None:
                return web.Response(status=200)
            return res

    async def get_url(self):
        return self.url

logger.info("Creating BotHTTPServer")
Object = BotHTTPServer()
