import json
import logging
import asyncio
import string
import random


from collections import defaultdict

from matrixroom import MatrixRoom

import gitlab.formatting as fmt


HELP_DESC = ("!gitlab\t\t\t-\tGitlab Webhook Manager/Notifier 🦊\n")

DEFAULTCONFIG = {
    "emoji": True,
    "notification": True,
}

class LocalHookManager:
    """
    A HookManager loads and stores secrettokens and registers them to the
    global GitLabManager
    """

    def __init__(self, plugin):
        self.plugin = plugin
        self.tokens = defaultdict(list)
        self.glm = self.plugin.bot.get_global_plugin_object("gitlab_manager")

    async def load_tokens(self):
        if "gitlabtokens" in await self.plugin.kvstore_get_local_keys():
            jsondata = await self.plugin.kvstore_get_local_value("gitlabtokens")
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
            await self.plugin.kvstore_set_local_value("gitlabtokens", jsondata)

    async def add_token(self, token, store=True):
        tokenid = await self.glm.register_hook(token, self)
        self.tokens[tokenid] = token
        if store:
            await self.store_tokens()

    async def rem_token(self, tokenid):
        if tokenid in self.tokens:
            token = self.tokens[tokenid]
            await self.glm.deregister_hook(token, tokenid)
            self.tokens.pop(tokenid)
            await self.store_tokens()
            return True
        else:
            return False

    async def handle(self, token, event, content):
        """
        called by GitLabManager when a hook event occurs
        """
        logging.info(f"Token event received: {event}")
        if "config" in await self.plugin.kvstore_get_local_keys():
            config = json.loads(await self.plugin.kvstore_get_local_value("config"))
        else:
            config = DEFAULTCONFIG
        text = fmt.format_event(
            event, content, verbose=False, emojis=config['emoji'], asnotice=config['notification'])
        # await self.plugin.send_notice(text)
        if text is not None:
            if config['notification']:
                await self.plugin.send_htmlnotice(text)
            else:
                await self.plugin.send_html(text)
        # await self.plugin.send_htmlnotice(text)
        # await self.plugin.send_html(text)
        # text = format_event(event, content, verbose=True, use="text") # defined at the bottom
        # await self.plugin.send_notice(text)
        # await self.plugin.send_text(text)
        # await self.plugin.send_html(text)


async def destructor(plugin):
    self.glm.tokens = defaultdict(list)
    self.glm.currenthid = 0


async def register_to(plugin):
    subcommands = """gitlab [subcommand] [option1 option2 ...]
Available subcommands:
    newhook                 - generate secrettoken for a new webhooks
    remhook hooknbr         - remove a webhook subscription
    listhooks               - show subscribed webhooks
    config                  - change the way that notifications are printed

How does it work? 🦊
    You first create a new secret token for a hook using the 'newhook' command.
    Then open your gitlab repo (or group) page and navigate to 'Settings>Webhooks'.
    There, you enter the url and secret token returned by the 'newtoken'
    command and enter all event types you want to get notifications for and
    press 'Add webhook'.

See <a href="https://docs.gitlab.com/ee/user/project/integrations/webhooks.html">here</a> for more information on gitlab webhooks.
"""

    lhm = LocalHookManager(plugin)
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
        glm = lhm.glm
        url = glm.url + glm.path
        await lhm.add_token(token)
        text = f"Successfully created token."
        await plugin.send_text(text)
        html = f"URL: {url}\ntoken: {token}\n"
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
        html = "\n".join(f"{tokenid} - " + token[:4] + (len(token)-4)*"*"
                         for (tokenid, token) in lhm.tokens.items())+"\n"
        await plugin.send_html(format_help(html))

    async def handle_config(args):
        # setup default config
        if "config" not in await plugin.kvstore_get_local_keys():
            await plugin.kvstore_set_local_value("config", json.dumps(DEFAULTCONFIG))

        config = json.loads(await plugin.kvstore_get_local_value("config"))
        if len(args) == 0:
            await plugin.send_html(format_help("\n".join(f"{k}:\t{v}" for k,v
                in config.items()) + "\nPlease use !gitlab config set KEY VAL for changing a value"))
        elif len(args) == 3 and args[0] == "set" and args[1] in config and args[2].lower() in ["true", "false"]:
            config[args[1]] = (args[2].lower() == "true")
            await plugin.kvstore_set_local_value("config", json.dumps(config))
            await plugin.send_text(f"Successfully changed {args[1]} to {args[2]}")
        else:
            await plugin.send_text("Please use !gitlab config set <key> <val> for changing a value")

    async def gitlab_callback(room, event):
        #        fmttest='''Thomas(thomas@example.com) pushed to branch master of project cyber-slurm https://gitlab.rbg.tum.de/cyber/cyber-slurm/-/tree/master
        #- Fix bug 1 (test.com)
        #- Fix readme (test.com)
        #'''
        # await plugin.send_notice(fmttest)
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
        elif args[0] == "config":
            args.pop(0)
            await handle_config(args)
        else:
            await show_help()

    gitlab_handler = plugin.CommandHandler("gitlab", gitlab_callback)
    plugin.add_handler(gitlab_handler)
