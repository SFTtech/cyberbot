import json
import logging
import asyncio
import random
import string


from pprint import pprint
from collections import defaultdict

from aiohttp import web

from matrixroom import MatrixRoom


HELP_DESC = ("!gitlab\t\t\t-\tGitlab Webhook Manager/Notifier\n")


# Configuration
ADDRESS = "*"
HTTPPORT = 8080
HTTPSPORT = 4430
PREFERHTTPS = False
PATH = "/webhook" # unused

# Change these if you are running bernd behind a reverse proxy or you do some
# port magic
import socket
HTTPURL  = f"http://{socket.getfqdn()}"
if HTTPPORT != 80:
    HTTPURL  += f":{HTTPPORT}"
HTTPSURL = f"https://{socket.getfqdn()}"
if HTTPSPORT != 443:
    HTTPSURL  += f":{HTTPSPORT}"



class WebhookListener:
    """
    The WebhookListener creates a http and https server, listens to gitlab
    webhooks and triggers handler for the webhooks. It should be global and
    shared between multiple plugin instances

    TODO: Add logging to everything
    TODO: should be destoyed when a reload is triggered
    """

    def __init__(self,
            address="*",
            http_port="80",
            https_port="443"):
        self.tokens = defaultdict(list) # maps a secrettoken on a list of handlers
        self.is_running = False
        self.currenthid = 0 # unique ids for new hooks

        self.address = address
        self.http_port = http_port
        self.https_port = https_port
        

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
                handlers = [handler for (hid,handler) in self.tokens[token]]
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
        self.runner = web.ServerRunner(self.server)
        await self.runner.setup()

        self.http_site = web.TCPSite(self.runner, self.address, self.http_port)
        self.https_site = web.TCPSite(self.runner, self.address, self.https_port) # TODO: USE TLS
        await self.http_site.start()
        await self.https_site.start()

        self.is_running = True

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
        self.tokens[secrettoken].append((hookid,handler))
        return hookid

    async def deregister_hook(self, token, hookid):
        # TODO: Race Conditions?
        h = self.tokens[token]
        for i in range(len(h)):
            if h[i][0] == hookid:
                del h[i]
                pprint("After del")
                pprint(h)
                break


class LocalHookManager:
    """
    A LocalHookManager loads and stores secrettokens and registers them to the
    webhooklistener
    """
    def __init__(self, plugin, whl):
        """
        whl: webhook listener
        """
        self.plugin = plugin
        self.tokens = defaultdict(list)
        self.whl = whl

    async def load_tokens(self):
        if "gitlabtokens" in await self.plugin.kvstore_get_keys():
            jsondata = await self.plugin.kvstore_get_value("gitlabtokens")
            try:
                tokenlist = json.loads(jsondata)
            except:
                tokenlist = []
        else:
            tokenlist = []

        if self.tokens is None:
            self.tokens = defaultdict(list)

        for token in tokenlist:
            await self.add_token(token, store=False)

    async def store_tokens(self):
        if self.tokens is not None:
            jsondata = json.dumps(list(self.tokens.values()))
            await self.plugin.kvstore_set_value("gitlabtokens", jsondata)

    async def add_token(self, token, store=True):
        tokenid = await self.whl.register_hook(token, self)
        self.tokens[tokenid] = token
        if store:
            await self.store_tokens()

    async def rem_token(self, tokenid):
        pprint(self.tokens)
        if tokenid in self.tokens:
            token = self.tokens[tokenid]
            await self.whl.deregister_hook(token, tokenid)
            self.tokens.pop(tokenid)
            await self.store_tokens()
            return True
        else:
            return False

    async def handle(self, token, event, content):
        """
        called by WebhookListener when a hook event occurs
        """
        logging.info(f"Token event received: {event}")
        text = format_event(event, content) # defined at the bottom
        await self.plugin.send_notice(text)





if "webhook_listener" not in globals():
    logging.info("Creating WebhookListener")
    webhook_listener = WebhookListener(address=ADDRESS,
                                       http_port=HTTPPORT,
                                       https_port=HTTPSPORT)
    # has to be started from an async context
    # this happens in the first register_to call


async def destructor(plugin):
    webhook_listener.tokens = defaultdict(list)
    webhook_listener.currenthid = 0



async def register_to(plugin):

    subcommands = """gitlab [subcommand] [option1 option2 ...]
Available subcommands:
    newhook                 - generate secrettoken for a new webhooks
    remhook hooknbr         - remove a webhook subscription
    listhooks               - show subscribed webhooks

How does it work?
    You first create a new secret token for a hook using the 'newhook' command.
    Then open your gitlab repo (or group) page and navigate to 'Settings>Webhooks'.
    There, you enter the url and secret token returned by the 'newtoken'
    command and enter all event types you want to get notifications for and
    press 'Add webhook'.

See <a href="https://docs.gitlab.com/ee/user/project/integrations/webhooks.html">here</a> for more information on gitlab webhooks.
"""

    if not webhook_listener.is_running:
        await webhook_listener.start()

    lhm = LocalHookManager(plugin, webhook_listener)
    await lhm.load_tokens()


    def format_help(text):
        html_text = "<pre><code>" + text + "</code></pre>\n"
        return html_text

    async def show_help():
        formatted_subcommands = format_help(subcommands)
        await plugin.send_html(formatted_subcommands, subcommands)


    async def handle_newhook(args):
        chars = string.ascii_letters + string.digits
        n = 16
        token = "".join(random.choice(chars) for i in range(n))
        if PREFERHTTPS:
            url = HTTPSURL + PATH
        else:
            url = HTTPURL + PATH
        await lhm.add_token(token)
        text = f"Successfully created token."
        await plugin.send_text(text)
        html = f"URL: {url}\ntoken: {token}"
        await plugin.send_html(format_help(html))


    async def handle_remhook(args):
        if not args:
            await show_help()
        else:
            if await lhm.rem_token(args[0]):
                await plugin.send_text("Successfully removed token")
            else:
                await plugin.send_text("Invalid Tokennr")
            

    async def handle_listhooks(args):
        html = "\n".join(f"{tokenid} - " + token[:4] + (len(token)-4)*"*" \
                for (tokenid,token) in lhm.tokens.items())
        await plugin.send_html(format_help(html))


    async def gitlab_callback(room, event):
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




























def format_event(event, content):
    # from gghttps://docs.gitlab.com/ee/user/project/integrations/webhooks.html
    events = ["Push Hook",
            "Tag Push Hook",
            "Issue Hook",
            "Note Hook",
            "Merge Request Hook",
            "Wiki Page Hook",
            "Pipeline Hook",
            "Job Hook"]


    # PUSH HOOK
    if event == "Push Hook":
        user_name = content['user_name']
        user_email = content['user_email']
        ref = content['ref']
        project = content['project']['name']
        commits = [commit['title'] for commit in content['commits']]
        if len(content['commits']):
            lastcommiturl = content['commits'][0]['url']
            committitle = commits[0]
        else:
            lastcommiturl = ""
            committitle = ""
        return f"{user_name}({user_email}) pushed to branch {ref} of {project}: {committitle}, {lastcommiturl}"


    # TAG PUSH HOOK
    if event == "Tag Push Hook":
        user_name = content['user_name']
        ref = content['ref']
        project = content['project']['name']
        projecturl = content['project']['web_url']
        return f"{user_name} pushed tag {ref} of {project}: {projecturl}"


    # ISSUE HOOK
    if event == "Issue Hook":
        # TODO: find out when opened/closed/changed
        user_name = content['user']['name']
        ref = content['ref']
        oa = content['object_attributes']
        issuetitle = oa['title']
        issueurl = oa['url']
        issueid = oa['iid']
        project = content['project']['name']
        projecturl = content['project']['web_url']
        return f"issue #{iid} {issuetitle} in {project} changed: {issueurl}"

    # TODO: note hook
    # TODO: merge request hook
    # TODO: wiki hook
    # TODO: pipeline hook
    # TODO: job hook

    return "Unknown event received: {event}. Please poke the maintainers."
