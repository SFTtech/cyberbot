import json
import logging
import asyncio
import string
import random
import configparser
import sys

from collections import defaultdict

from aiohttp import web

from matrixroom import MatrixRoom

class GitLabManager:
    def __init__(self):
        self.tokens = defaultdict(list)
        self.bot = None
        self.http_server = None
        self.currenthid = 0
        self.url = ""

    async def set_bot(self, bot):
        self.bot = bot
        self.http_server = self.bot.get_global_plugin_object("http_server")
        if "gitlab_manager" not in self.bot.config or "path" not in self.bot.config["gitlab_manager"]:
            logging.error("gitlab_manager: invalid config file section")
            sys.exit(-1)
        self.config = self.bot.config["gitlab_manager"]

        p = self.config["path"]
        self.path = "/" + p if not p.startswith("/") else p
        self.url = await self.http_server.get_url()

    async def start(self):
        async def handle_request(request):
            if request.method == "GET":
                logging.info(f"Gitlab: Got GET request to webhook. Sending ooops page.")
                text = """
<html>
    <head>
        <title>Ooooooooooops</title>
    </head>

    <body>
        <p>Please don't open the url in your browser, but rather paste the url and the token into your page's gitlab webhook settings under Settings/Webhooks.</p>
    </body>
</html>
"""
                return web.Response(text=text, content_type='text/html')

            if request.path != self.path:
                logging.info(f"Gitlab: ignoring request to wrong path: {request.path}")
                return

            if request.method != "POST":
                return web.Response(status=404)

            token = request.headers.get("X-Gitlab-Token")
            event = request.headers.get("X-Gitlab-Event")
            if token is None or event is None:
                return web.Response(status=400)

            if token in self.tokens:
                handlers = [handler for (hid, handler) in self.tokens[token]]
                c = await request.content.read()
                with open("hookslog.txt", "ab+") as f:
                    f.write(c)
                try:
                    jsondata = c.decode("utf-8")
                    content = json.loads(jsondata)
                except UnicodeDecodeError:
                    return web.Response(status=400)
                except:
                    return web.Response(status=400)

                await asyncio.gather(
                    *(handler.handle(token, event, content) for handler in handlers))
                return web.Response(text="OK")
            return web.Response(status=400)

        
        res = await self.http_server.register_path(self.path, handle_request) 
        if (res == None):
            print("Failed registering github_manager path to http_server")

    async def nexthookid(self):
        self.currenthid += 1
        return str(self.currenthid)

    async def register_hook(self, secrettoken, handler):
        """
        handler has to be a async function and has to have a method
        called 'handle(token, event, content)' where event is
        the gitlab event and content ist the parsed json from the webhook post
        """
        hookid = await self.nexthookid()
        self.tokens[secrettoken].append((hookid, handler))
        return hookid

    async def deregister_hook(self, token, hookid):
        # Race Conditions? -> no, because only one thread and no await
        h = self.tokens[token]
        for i in range(len(h)):
            if h[i][0] == hookid:
                del h[i]
                break

logging.info("Creating GitLabManager")
Object = GitLabManager()
