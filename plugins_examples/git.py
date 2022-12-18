import json
import asyncio
import string
import random

from collections import defaultdict


from matrixroom import MatrixRoom

DEFAULTCONFIG = {
    "emoji": True,
    "notification": True,
}


class LocalHookManager:
    """
    A HookManager loads and stores secrettokens and registers them to the
    global GitManager
    Can be used to register different plugins, e.g. the gitlab or the github plugin
    One only needs to provide which endpoint to use and how to format the received events
    """

    def __init__(
        self, plugin, git: str, format_event_func, url: str, emoji="🦊", important=""
    ):
        """
        git: the git endpoint to use, e.g. gitlab or github
        """
        self.plugin = plugin
        self.tokens = defaultdict(list)
        self.git_manager = self.plugin.bot.get_global_plugin_object(f"{git}_manager")
        self.git = git
        self.store_key = f"{git}tokens"
        self.format_event = format_event_func
        self.url = url
        self.emoji = emoji
        self.important = important

    async def load_tokens(self):
        if self.store_key in await self.plugin.kvstore_get_local_keys():
            jsondata = await self.plugin.kvstore_get_local_value(self.store_key)
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
            await self.plugin.kvstore_set_local_value(self.store_key, jsondata)

    async def add_token(self, token, store=True):
        tokenid = await self.git_manager.register_hook(token, self)
        self.tokens[tokenid] = token
        if store:
            await self.store_tokens()

    async def rem_token(self, tokenid):
        if tokenid in self.tokens:
            token = self.tokens[tokenid]
            await self.git_manager.deregister_hook(token, tokenid)
            self.tokens.pop(tokenid)
            await self.store_tokens()
            return True
        else:
            return False

    async def handle(self, token, event, content):
        """
        called by GitManager when a hook event occurs
        """
        self.plugin.log.info(f"Token event received: {event}")
        if "config" in await self.plugin.kvstore_get_local_keys():
            config = json.loads(await self.plugin.kvstore_get_local_value("config"))
        else:
            config = DEFAULTCONFIG
        text = self.format_event(
            event,
            content,
            verbose=False,
            emojis=config["emoji"],
            asnotice=config["notification"],
        )
        if text is not None:
            if config["notification"]:
                await self.plugin.send_htmlnotice(text)
            else:
                await self.plugin.send_html(text)

    async def start(self):
        help_text = """!{git} [subcommand] [option1 option2 ...]
    Available subcommands:
        newhook                 - generate secrettoken for a new webhooks
        remhook hooknbr         - remove a webhook subscription
        listhooks               - show subscribed webhooks
        config                  - change the way that notifications are printed

    How does it work? {emoji}
        You first create a new secret token for a hook using the 'newhook' command.
        Then open your {git} repo (or group) page and navigate to 'Settings>Webhooks'.
        There, you enter the url and secret token returned by the 'newtoken'
        command and enter all event types you want to get notifications for and
        press 'Add webhook'.

    See "{url}" for more information on {git} webhooks.
    """.format(
            git=self.git, emoji=self.emoji, url=self.url
        )

        def format_code(text):
            html_text = "<pre><code>" + text + "</code></pre>\n"
            return html_text

        async def show_help():
            formatted_help = format_code(help_text)
            await self.plugin.send_html(formatted_help, help_text)

        async def handle_newhook(args, event):
            chars = string.ascii_letters + string.digits
            n = 16
            token = "".join(random.choice(chars) for i in range(n))
            url = self.git_manager.url + self.git_manager.path
            await self.add_token(token)
            text = f"Successfully created token."
            await self.plugin.send_text(text)
            html = f"URL: {url}\ntoken: {token}\n{self.important}"
            await self.plugin.send_html_to_user(event.sender, format_code(html))

        async def handle_remhook(args):
            if not args:
                await show_help()
            else:
                if await self.rem_token(args[0]):
                    await self.plugin.send_text("Successfully removed token")
                else:
                    await self.plugin.send_text("Invalid Tokennr")

        async def handle_listhooks(args):
            html = (
                "\n".join(
                    f"{tokenid} - " + token[:4] + (len(token) - 4) * "*"
                    for (tokenid, token) in self.tokens.items()
                )
                + "\n"
            )
            await self.plugin.send_html(format_code(html))

        async def handle_config(args):
            # setup default config
            if "config" not in await self.plugin.kvstore_get_local_keys():
                await self.plugin.kvstore_set_local_value(
                    "config", json.dumps(DEFAULTCONFIG)
                )

            config = json.loads(await self.plugin.kvstore_get_local_value("config"))
            if len(args) == 0:
                await self.plugin.send_html(
                    format_code(
                        "\n".join(f"{k}:\t{v}" for k, v in config.items())
                        + f"\nPlease use !{self.git} config set <ke> <val> for changing a value"
                    )
                )
            elif (
                len(args) == 3
                and args[0] == "set"
                and args[1] in config
                and args[2].lower() in ["true", "false"]
            ):
                config[args[1]] = args[2].lower() == "true"
                await self.plugin.kvstore_set_local_value("config", json.dumps(config))
                await self.plugin.send_text(
                    f"Successfully changed {args[1]} to {args[2]}"
                )
            else:
                await self.plugin.send_text(
                    f"Please use !{self.git} config set <key> <val> for changing a value"
                )

        async def git_callback(room, event):
            #        fmttest='''Thomas(thomas@example.com) pushed to branch master of project cyber-slurm https://gitlab.rbg.tum.de/cyber/cyber-slurm/-/tree/master
            # - Fix bug 1 (test.com)
            # - Fix readme (test.com)
            #'''
            # await plugin.send_notice(fmttest)
            args = self.plugin.extract_args(event)
            args.pop(0)
            if len(args) == 0:
                await show_help()
            elif args[0] == "newhook":
                args.pop(0)
                await handle_newhook(args, event)
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

        await self.load_tokens()
        git_handler = self.plugin.CommandHandler(self.git, git_callback)
        self.plugin.add_handler(git_handler)


# TODO use the not yet implemented register_destructor
async def destructor(plugin):
    self.git_manager.tokens = defaultdict(list)
    self.git_manager.currenthid = 0
