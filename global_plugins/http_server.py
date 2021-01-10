import logging
import sys
import configparser
from aiohttp import web

CONFIGPATH = "global_plugins/config/http_server.ini"

class BotHTTPServer:

    def __init__(self, bind_address, bind_port):
        self.bind_address = bind_address
        self.bind_port = bind_port
        self.registered_paths = {}
        self.bot = None

    async def set_bot(self, bot):
        self.bot = bot

    async def start(self):
        self.server = web.Server(self.handle_request)
        self.runner = web.ServerRunner(self.server)
        await self.runner.setup()

        self.site = web.TCPSite(self.runner, self.bind_address, self.bind_port)
        await self.site.start()

    async def register_path(self, path, handler):
        """Returns the registered path e.g. for localhost/hallo/ -> hallo. None if path already has been registered."""
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

def read_config_and_initialize():
    logging.info("Creating BotHTTPServer")
    logging.info("Reading http_server config")

    config = configparser.ConfigParser()
    config.read(CONFIGPATH)

    if not 'BotHTTPServer' in config.sections():
        logging.error("""Bad config file. Please check that
config file exists and all fields are available\n""")
        sys.exit(-1)

    vals = config['BotHTTPServer']
    return BotHTTPServer(vals.get("BIND_ADDRESS", "localhost"), int(vals.get("BIND_PORT", "8080")))


Object = read_config_and_initialize()
