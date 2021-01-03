from aiohttp import web


class BotHTTPServer:


    def __init__(self, bind_address, bind_port):
        self.bind_address = bind_address
        self.bind_port = bind_port
        self.registered_paths = {}

    async def start(self):
        self.server = web.Server(self.handle_request)
        self.runner = web.ServerRunner(self.server)
        await self.runner.setup()

        self.site = web.TCPSite(self.runner, self.bind_address, self.bind_port)
        await self.site.start()

    async def register_path(self, path, handler):
        """Returns the registered path e.g. for localhost/hallo/ -> hallo. None if path aljeady has been registered."""
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
