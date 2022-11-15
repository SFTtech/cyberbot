import logging
import asyncio
import nio
from aiohttp import web

class InviteManager:

    def __init__(self):
        self.bot = None
        self.invitations = {}
        self.path = ""
        self.config = {}
        self.http_server = None

    async def set_bot(self, bot):
        self.bot = bot
        self.http_server = self.bot.get_global_plugin_object("http_server")
        if "invite_manager" not in self.bot.config or "path" not in self.bot.config["invite_manager"]:
            logging.error("invite_manager: invalid config file section")
            sys.exit(-1)
        self.config = self.bot.config["invite_manager"]

        p = self.config["path"]
        self.path = "/" + p if not p.startswith("/") else p

    async def start(self):
        async def handle_request(request):
            def gen_html(msg):
                return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Success</title>
    <meta charset="utf-8">
</head>

<body>
    <p>{msg}</p>
</body>
</html>
"""
            if not request.path.endswith("/"):
                path = request.path + "/"
            else:
                path = request.path

            token = path.split("/")[-2]
            if (token not in self.invitations.keys()):
                return web.Response(text=gen_html("Invalid Link"), content_type='text/html')
            room_id, invitor = self.invitations[token]
            room = self.bot.client.rooms.get(room_id)
            if request.method == "GET":
                if room is None:
                    room_name = "Unknown Room (Probably will fail to join)"
                else:
                    room_name = room.display_name
                content = gen_site_content(room_name, invitor)
                return web.Response(text=content, content_type='text/html')
            elif request.method == "POST":
                params = await request.post()
                if "userid" not in params:
                    return web.Response(status=400)
                user_id = params["userid"].strip()
                if not user_id.startswith("@"):
                    user_id = "@" + user_id
                if room is None:
                    return web.Response(text=gen_html("Failed to send invitation (Bot is not member of the room)."), content_type='text/html')
                res = (await self.bot.client.room_invite(room_id, user_id))
                if type(res) == nio.responses.RoomInviteError:
                    return web.Response(text=gen_html(f"Failed to send invitation: {res.message}."), content_type='text/html')
                return web.Response(text=gen_html("Check your matrix client for a new invitation."), content_type='text/html')

        res = await self.http_server.register_path(self.path, handle_request)
        if (res == None):
            print("Failed registering invite_manager path to http_server")

    async def register_invitation(self, token, room_id, invitor):
        self.invitations[token] = (room_id, invitor)

    async def deregister_invitation(self, token):
        del self.invitations[token]

logging.info("Creating InviteManager")
Object = InviteManager()


def gen_site_content(room_name, inviter_display_name):
    return f"""
<!DOCTYPE html>
<html>
    <head>
        <title>Matrix Invitation to {room_name}</title>
        <meta charset="utf-8">
    </head>

    <body>
        <p>You are invited by <b>{inviter_display_name}</b> to join Matrix room <code>{room_name}</code>.</p>
        <p>You will receive an invitation in your Matrix client after you submit your <b>Matrix UserID</b> in the box below.</p>
        <p><form method=post>
            <input type=text placeholder="e.g. @rofl:cit.tum.de" name=userid />
            <input type=submit value="Request Invite"/> (This may take some time (~10s))
        </form></p>
        <p>Your Matrix User ID is in the form of <code>@username:servername.tld</code>.
        You can see your ID when pressing on the top left icon in Element!</p>
    </body>
</html>
    """
