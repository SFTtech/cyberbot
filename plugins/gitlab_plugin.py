import json
import logging
import aiohttp

from matrixroom import MatrixRoom
from pprint import pprint

HELP_DESC = ("!gitlab\t\t\t-\tGitlab Webhook Manager/Notifier\n")


# Change these if you are running bernd behind a reverse proxy
import socket
HTTPURL  = f"http://{socket.getfqdn()}"
HTTPSURL = f"https://{socket.getfqdn()}"

IP = "0.0.0.0"
HTTPPORT = 80
HTTPSPORT = 443
HTTP = True
HTTPS = True


class GlobalHookManager:
    """
    The GlobalHookManager loads/stores hooks, listens to webhooks and can be
    used to create a LocalHookManager. It is shared among multiple rooms
    """
    async def loadhooks(self):
        # use matrixbot's database for that
        pass

    async def registerLHM(self, lhm):
        # register a local hook manager
        pass


    class LocalHookManager:
    """
    Each room has a localhookmanager that talks with the GlobalHookManager
    """
        def __init__(self):
            pass

    def __init__(self):
        pass

    async def addhook(self, token):
        pass







if "gl" not in globals():
    print("creating gl")
    gl = GlobalListener()







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
