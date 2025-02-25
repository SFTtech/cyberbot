import json
import random
import string
from collections import defaultdict

HELP_DESC = "!invite\t\t\t-\tGenerate invitation link for current room. Will direct to a website where people can enter their user_id and be invited by the bot.\n"


class LocalInviteManager:
    def __init__(self, plugin):
        self.plugin = plugin
        self.tokens = defaultdict(list)
        self.im = self.plugin.bot.get_service("invite_manager")
        self.currenttokenid = 0

    async def load_tokens(self):
        if "invitetokens" in await self.plugin.kvstore_get_local_keys():
            jsondata = await self.plugin.kvstore_get_local_value("invitetokens")
            try:
                tokenlist = json.loads(jsondata)
            except:
                tokenlist = []
        else:
            tokenlist = []

        if self.tokens is None:
            self.tokens = defaultdict(list)

        for token, invitor in tokenlist:
            await self.add_token(token, invitor, store=False)

    async def store_tokens(self):
        if self.tokens is not None:
            jsondata = json.dumps(list(self.tokens.values()))
            await self.plugin.kvstore_set_local_value("invitetokens", jsondata)

    async def nexttokenid(self):
        self.currenttokenid += 1
        return str(self.currenttokenid)

    async def add_token(self, token, invitor, store=True):
        await self.im.register_invitation(token, self.plugin.mroom.room_id, invitor)
        tokenid = await self.nexttokenid()
        self.tokens[tokenid] = (token, invitor)
        if store:
            await self.store_tokens()

    async def rem_token(self, tokenid):
        if tokenid in self.tokens:
            token, invitor = self.tokens[tokenid]
            await self.im.deregister_invitation(token)
            self.tokens.pop(tokenid)
            await self.store_tokens()
            return True
        else:
            return False


async def init(plugin):
    subcommands = """invite [subcommand]
Available subcommands:
    new     - generate new invitation link
    rm #nr  - deactivate an invitation link
    list    - show invitation links
"""

    lim = LocalInviteManager(plugin)
    await lim.load_tokens()

    def format_help(text):
        html_text = "<pre><code>" + text + "</code></pre>\n"
        return html_text

    async def show_help():
        formatted_subcommands = format_help(subcommands)
        await plugin.send_html(formatted_subcommands, subcommands)

    async def handle_new(event, args):
        def gen_random_token():
            # TODO: check for collisions
            chars = string.ascii_letters + string.digits
            n = 32
            return "".join(random.choice(chars) for i in range(n))

        async def gen_url(token):
            url = await lim.im.http_server.get_url()
            return f"{url}{lim.im.path}/{token}/"

        token = gen_random_token()
        try:
            invitor = await plugin.get_sender_user_name(event)
        except:
            invitor = "Unknown Invitor"
        await lim.add_token(token, invitor)

        await plugin.send_text_to_user(
            event.sender,
            html=("Send this link to the people you want to invite to this room: <br/><pre><code>"
                  f"{await gen_url(token)}"
                  "</pre></code>"),
        )

    async def handle_rm(args):
        if not args:
            await show_help()
        elif await lim.rem_token(args[0]):
            await plugin.send_text("Successfully deleted invitation")
        else:
            await plugin.send_text("Invalid invitation number")

    async def handle_list(args):
        html = (
                "\n".join(f"{tokenid} - ({token[0][:10] + '*'*22} - {token[1]})" for (tokenid, token) in lim.tokens.items())
            + "\n"
        )
        await plugin.send_html(format_help(html))

    async def invite_callback(room, event):
        args = plugin.extract_args(event)
        args.pop(0)
        if len(args) == 0:
            await show_help()
        elif args[0] == "new":
            args.pop(0)
            await handle_new(event, args)
        elif args[0] == "rm":
            args.pop(0)
            await handle_rm(args)
        elif args[0] == "list":
            args.pop(0)
            await handle_list(args)
        else:
            await show_help()

    invite_handler = plugin.CommandHandler("invite", invite_callback)
    plugin.add_handler(invite_handler)
