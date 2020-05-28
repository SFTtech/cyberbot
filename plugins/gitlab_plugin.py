import json
import logging
import asyncio
import random
import string
import configparser


from pprint import pprint
from collections import defaultdict

from aiohttp import web

from matrixroom import MatrixRoom


HELP_DESC = ("!gitlab\t\t\t-\tGitlab Webhook Manager/Notifier 🦊\n")


# Configuration
CONFIGPATH = "./plugins/gitlab.ini"
DEFAULTADDRESS = "*"
DEFAULTPORT = 8080
DEFAULTPATH = "/webhook" # unused



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
            port="8080",
            url="localhost",
            path="/webhook"):
        self.tokens = defaultdict(list) # maps a secrettoken on a list of handlers
        self.is_running = False
        self.currenthid = 0 # unique ids for new hooks

        self.address = address
        self.port = port
        self.url = url
        self.path = path
        

    async def start(self):
        """
        start servers
        """
        if self.is_running:
            return

        async def handle_request(request):
            if request.path != self.path:
                logging.info(f"Gitlab: ignoring request to wrong path: {request.path}")
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

        self.site = web.TCPSite(self.runner, self.address, self.port)
        await self.site.start()

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
        text = format_event(event, content, verbose=True, use="html") # defined at the bottom
        #await self.plugin.send_notice(text)
        await self.plugin.send_html(text)
        await self.plugin.send_htmlnotice(text)
        #await self.plugin.send_html(text)
        #text = format_event(event, content, verbose=True, use="text") # defined at the bottom
        #await self.plugin.send_notice(text)
        #await self.plugin.send_text(text)
        #await self.plugin.send_html(text)




if "webhook_listener" not in globals():
    logging.info("Creating WebhookListener")
    logging.info("Reading gitlab config")

    config = configparser.ConfigParser()
    config.read(CONFIGPATH)
    if "server" not in config or "exposed" not in config or \
        "address" not in config["server"] or "port" not in config["server"] or \
        "url" not in config["exposed"] or "path" not in config["exposed"]:
        logging.warning("Gitlab: invalid config file, falling back to defaults")
        config["server"] = {
                "address" : DEFAULADDRESS,
                "port" : DEFAULTPORT,
            }
        config["exposed"] = {
                "url" : "http" + DEFAULADDRESS + f":{DEFAULTPORT}",
                "path" : DEFAULTPATH,
            }
    p = config["exposed"]["path"]
    p = "/" + p if not p.startswith("/") else p
    webhook_listener = WebhookListener(address=config["server"]["address"],
                                       port=int(config["server"]["port"]),
                                       url=config["exposed"]["url"],
                                       path=p)
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

How does it work? 🦊
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
        url = webhook_listener.url + webhook_listener.path
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
#        fmttest='''Thomas(thomas@example.com) pushed to branch master of project cyber-slurm https://gitlab.rbg.tum.de/cyber/cyber-slurm/-/tree/master
#- Fix bug 1 (test.com)
#- Fix readme (test.com)
#'''
        #await plugin.send_notice(fmttest)
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




























def format_event(event, content, verbose=True, use="markdown"):
    # the use parameter should toggle different styles in the future (greyed
    # out, verbose, emojis, ...)
    # and make the verbose flag obsolete
    # from https://docs.gitlab.com/ee/user/project/integrations/webhooks.html
    events = ["Push Hook",
            "Tag Push Hook",
            "Issue Hook",
            "Note Hook",
            "Merge Request Hook",
            "Wiki Page Hook",
            "Pipeline Hook",
            "Job Hook"]
    #animals = "🐶🐺🦊🦝🐱🐱🦁🐯"
    animals = "🦊"
    animal = random.choice(animals)


    # PUSH HOOK
    if event == "Push Hook":
        user_name = content['user_name']
        user_email = content['user_email']
        if "ref" in content:
            ref = content['ref']
        else:
            ref = ""
        branch = ref.split("/")[-1]
        if "project" in content:
            projectname = content['project']['name']
            projecturl = content['project']['web_url']
        else:
            projectname = ""
        if not "commits" in content:
            commits = []
        else:
            commits = content['commits']

        if commits:
            lastcommiturl = content['commits'][0]['url']
            lastcommittitle = commits[0]
        else:
            lastcommiturl = ""
            lastcommittitle = ""

        if not verbose:
            return f'{animal} {user_name}({user_email}) pushed to 🌿 {branch} of {projectname}: {lastcommittitle}, {lastcommiturl}'
        else:
            if use.lower() == "html":
                s =  f"{animal} {user_name} (<a href='mailto:{user_email}'>{user_email}</a>) pushed to 🌿 {branch} of <a href={projecturl}>{projectname}</a><ul>\n"
                s += "\n".join(f"<li>{commit['title']} (<a href={commit['url']}>{commit['id'][:7]}</a>)</li>" for commit in commits)
                s += "</ul>"
            else:
                s =  f"{animal} {user_name}({user_email}) pushed to 🌿 {branch} of {projectname} {projecturl}\n"
                s += "\n".join(f"* {commit['title']} ({commit['url']})" for commit in commits)
        return s


    # TAG PUSH HOOK
    if event == "Tag Push Hook":
        user_name = content['user_name']
        user_email = content['user_email']
        zeroes = "0000000000000000000000000000000000000000"
        if content['after'] == zeroes:
            action = "deleted"
        elif content['before'] == zeroes:
            action = "pushed new"
        else:
            action = "changed"
        if "ref" in content:
            ref = content['ref']
        else:
            ref = ""
        tagname = ref.split("/")[-1]
        project = content['project']['name']
        projecturl = content['project']['web_url']
        return f"{animal} {user_name} ({user_email}) {action} remote 🏷{tagname} n <a href={projecturl}>{project}</a>"


    # ISSUE HOOK
    if event == "Issue Hook":
        user_email = content['user']['email']
        user_name = content['user']['name']
        if "ref" in content:
            ref = content['ref']
        else:
            ref = ""
        oa = content['object_attributes']
        issuetitle = oa['title']
        issueurl = oa['url']
        issueid = oa['iid']
        action = oa['action']
        actionpassive = action + "ed" if "open" in action else action + "d" # opened and reopened
        new = "new issue" if action == "open" else "issue"
        #TODO: check confidential attribute
        #TODO: print exact changes (also labels, etc, description if new) when verbose is set
        project = content['project']['name']
        projecturl = content['project']['web_url']
        return f"{animal} {user_name} ({user_email}) {actionpassive} {new} <a href={issueurl}>#{issueid} {issuetitle}</a> in <a href={projecturl}>{project}</a>"

    # TODO: note hook
    # TODO: merge request hook
    # TODO: wiki hook
    # TODO: pipeline hook
    # TODO: job hook

    return f"Unknown event received: {event}. Please poke the maintainers."
