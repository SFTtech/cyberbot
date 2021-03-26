import json
import logging
import asyncio
import string
import random
import configparser
import sys
import hmac


from pprint import pprint
from collections import defaultdict

from aiohttp import web

from matrixroom import MatrixRoom

CONFIGPATH = "global_plugins/config/github_manager.ini"

class GitHubManager:
    def __init__(self, url, path):
        self.url = url
        self.path = path
        self.tokens = defaultdict(list)
        self.bot = None
        self.http_server = None
        self.currenthid = 0

    async def set_bot(self, bot):
        self.bot = bot
        self.http_server = self.bot.get_global_plugin_object("http_server") #pluginname like in the config file of global_plugins

    async def start(self):
        async def handle_request(request):
            if request.method == "GET":
                logging.info(f"Github: Got GET request to webhook. Sending ooops page.")
                text = """
<html>
    <head>
        <title>Ooooooooooops</title>
    </head>

    <body>
        <p>Please don't open the url in your browser, but rather paste the url and the token into your page's github webhook settings under Settings/Webhooks.</p>
    </body>
</html>
"""
                return web.Response(text=text, content_type='text/html')

            if request.path != self.path:
                logging.info(f"Github: ignoring request to wrong path: {request.path}")
                return

            if request.method != "POST":
                return web.Response(status=404)

            
            c = await request.content.read()
            with open("hookslog.txt", "ab+") as f:
                f.write(c)
            
            if ("X-Hub-Signature-256" not in request.headers):
                return web.Response(status=400)
            sig = request.headers.get("X-Hub-Signature-256").split("=")[1]
            if ("X-GitHub-Event" not in request.headers):
                return web.Response(status=400)
            event = request.headers.get("X-GitHub-Event")

            # how to check if not really is from github and simultaniously find out which token was used:
            # https://docs.github.com/en/developers/webhooks-and-events/securing-your-webhooks
            # we just check all tokens and if one has a matching hash, this is the one
            # linearly in number of tokens and slow as we compute a hash until we find the token
            # also probably vulnerable to timing attacks. But at the moment I don't have a better idea

            for token in self.tokens:
                h = hmac.new(bytes(token, encoding="utf8"), c, "sha256")
                if (hmac.compare_digest(h.hexdigest(), sig)):
                    handlers = [handler for (hid, handler) in self.tokens[token]]
                    try:
                        content = json.loads(c.decode("utf-8"))
                    except Exception as e:
                        print(e)
                        print(f"c: {c}")
                        print(f"content: {content}")
                        return web.Response(status=400)
                    await asyncio.gather(
                        *(handler.handle(token, event, content) for handler in handlers))
                    return web.Response(text="OK")
            return web.Response(status=400)

        res = await self.http_server.register_path(self.path, handle_request) 

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
                pprint("After del")
                pprint(h)
                break

def read_config_and_initialize():
    logging.info("Creating GitHubManager")
    logging.info("Reading github_manager config")

    config = configparser.ConfigParser()
    config.read(CONFIGPATH)
    if "exposed" not in config or \
            "url" not in config["exposed"] or "path" not in config["exposed"]:
        logging.error(
            "Github: invalid config file")
        sys.exit(-1)

    p = config["exposed"]["path"]
    p = "/" + p if not p.startswith("/") else p
    return GitHubManager(url=config["exposed"]["url"], path=p)

Object = read_config_and_initialize()
