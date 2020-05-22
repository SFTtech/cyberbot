import json
import logging
import asyncio


from pprint import pprint
from collections import defaultdict

from aiohttp import web

from matrixroom import MatrixRoom


HELP_DESC = ("!gitlab\t\t\t-\tGitlab Webhook Manager/Notifier\n")


# Configuration
ADDRESS = "0.0.0.0"
HTTPPORT = 80
HTTPSPORT = 443
PREFERHTTPS = True

# Change these if you are running bernd behind a reverse proxy
import socket
HTTPURL  = f"http://{socket.getfqdn()}"
HTTPSURL = f"https://{socket.getfqdn()}"



class WebhookListener:
    """
    The WebhookListener creates a http and https server, listens to gitlab
    webhooks and triggers handler for the webhooks. It should be global and
    shared between multiple plugin instances

    TODO: Add logging to everything
    """

    def __init__(self,
            address="0.0.0.0",
            http_port="80",
            https_port="443"):
        self.tokens = defaultdict(list) # maps a secrettoken on a list of handlers
        self.is_running = False

        self.address = address
        self.http_port = http_port
        self.https_port = https_port
        return self
        

    async def start(self):
        """
        start servers
        """
        if self.is_running:
            return

        async def handle_request(request):
            # TODO: check path
            if request.method != "POST":
                return web.Response(status=404)

            token = request.headers.get("X-Gitlab-Token")
            event = request.headers.get("X-Gitlab-Event")
            if token is None or event is None:
                return web.Response(status=400)

            if token in self.tokens:
                handlers = self.tokens[token]
                c = await request.content.read()
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

        self.server = web.Server(handle_request)
        self.runner = webServerRunner(self.server)
        await runner.setup()

        self.http_site = web.TCPSite(self.runner, self.address, self.http_port)
        self.https_site = web.TCPSite(self.runner, self.address, self.https_port)
        await self.http_site.start()
        await self.https_site.start()

        self.is_running = True


    async def register_hook(self, secrettoken, content):
        """
        handler has to be a async function and has to have a method
        called 'handle(token, event, content)' where event is
        the gitlab event and content ist the parsed json from the webhook post
        """
        tokens[secrettoken].append(handler)


class LocalHookManager:
    """
    A LocalHookManager loads and stores secrettokens and registers them to the
    webhooklistener
    """
    def __init__(self, plugin):
        self.plugin = plugin

    async def load_hooks(self):
        pass

    async def store_hooks(self):
        pass

    async def add_hook(self):
        pass

    async def rem_hook(self):
        pass

    async def handle(token, event, content):
        """
        called by WebhookListener when a hook event occurs
        """
        pass





if "webhook_listener" not in globals():
    logging.info("Creating WebhookListener")
    webhook_listener = WebhookListener(address=ADDRESS,
                                       http_port=HTTPPORT,
                                       https_port=HTTPSPORT)
    await webhook_listener.start()




async def register_to(plugin):


    subcommands = """gitlab [subcommand] [option1 option2 ...]
Available subcommands:
    newhook                 - generate secrettoken for a new webhooks
    remhook hooknbr         - remove a webhook subscription
    listhooks               - show subscribed webhooks

How does it work?
    You first create a new secret token for a hook using the 'newhook' command.
    Then open your gitlab repo page and navigate to 'Settings>Webhooks'.
    There, you enter the url and secret token returned by the 'newtoken'
    command and enter all event types you want to get notifications for and
    press 'Add webhook'.

See <a href="https://docs.gitlab.com/ee/user/project/integrations/webhooks.html">here</a> for more information on gitlab webhooks.
"""


    def format_help(text):
        html_text = "<pre><code>" + text + "</code></pre>\n"
        return html_text

    async def show_help():
        formatted_subcommands = format_help(subcommands)
        await plugin.send_html(formatted_subcommands, subcommands)


    async def handle_newhook(args):
        await plugin.send_notice("TODO")


    async def handle_remhook(args):
        await plugin.send_notice("TODO")
            

    async def handle_listhooks(args):
        await plugin.send_notice("TODO")


    async def gitlab_callback(room, event):
        print(id(gl))
        args = plugin.extract_args(event)
        args.pop(0)
        if len(args) == 0:
            await show_help()
        elif args[0] == "newhook":
            args.pop(0)
            await handle_newhook(args)
        elif args[0] == "remhook":
            args.pop(0)
            await handle_remhook(args)
        elif args[0] == "listhooks":
            args.pop(0)
            await handle_listhooks(args)
        else:
            await show_help()


    gitlab_handler = plugin.CommandHandler("gitlab", gitlab_callback)
    plugin.add_handler(gitlab_handler)
