from __future__ import annotations

import logging
import textwrap
from typing import TYPE_CHECKING

from aiohttp import web

from ..api.service import Service
from ..types import Err, Ok

if TYPE_CHECKING:
    from ...service.http_server import HTTPServer
    from ..bot import Bot
    from ..room import Room

logger = logging.getLogger(__name__)


class InviteManager(Service):
    def __init__(self, bot: Bot):
        super().__init__(bot)

        # {token -> (room_id, invitor)}
        self._invitations: dict[str, tuple[str, str]] = {}
        self._path = ""
        self._http_server: HTTPServer | None = None

    async def setup(self):
        self._http_server = self._bot.get_service("http_server")
        config = self._bot.get_config("invite_manager")

        self._path = config["invite_path"]
        if not self._path.startswith("/"):
            raise ValueError("webhook path must start with /")

    async def start(self):
        if not self._http_server:
            raise Exception("http server is not setup yet")

        res = await self._http_server.register_path(self._path, self._handle_request)
        if res is None:
            raise Exception("Failed registering invite_manager path to http_server")

    async def register_invitation(self, token, room_id, invitor):
        self._invitations[token] = (room_id, invitor)

    async def deregister_invitation(self, token):
        del self._invitations[token]

    async def _handle_request(self, subpath: str, request: web.BaseRequest) -> web.StreamResponse:
        token: str = subpath

        if not (invitation := self._invitations.get(token)):
            return web.Response(
                text=_message_page("Invalid Link"), content_type="text/html"
            )

        room_id, invitor = invitation
        room: Room | None = self._bot.rooms.get(room_id)

        match request.method:
            case "GET":
                if room is None:
                    room_name = "Unknown Room (Probably will fail to join)"
                else:
                    room_name = room.display_name

                content = _invite_page(room_name, invitor)
                return web.Response(text=content, content_type="text/html")

            case "POST":
                params = await request.post()
                if not (user_id := params.get("userid")):
                    return web.Response(status=400, text="userid parameter missing")
                if not isinstance(user_id, str):
                    return web.Response(status=400, text="userid must be a string")

                user_id = user_id.strip()
                if not user_id.startswith("@"):
                    user_id = f"@{user_id}"

                if room is None:
                    return web.Response(
                        text=_message_page(
                            "Failed to send invitation (Bot is not member of the room)."
                        ),
                        content_type="text/html",
                    )

                res = await room.invite(user_id)
                match res:
                    case Ok(_):
                        return web.Response(
                            text=_message_page("Check your matrix client for a new invitation."),
                            content_type="text/html",
                        )
                    case Err(msg):
                        return web.Response(
                            text=_message_page(f"Failed to send invitation: {msg}."),
                            content_type="text/html",
                        )
            case _:
                return web.Response(status=405, text="method not allowed")

def _message_page(msg):
    return textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html>
        <head>
            <title>Invite Manager</title>
            <meta charset="utf-8">
        </head>

        <body>
            <p>{msg}</p>
        </body>
    </html>
    """)

def _invite_page(room_name: str, inviter_display_name: str) -> str:
    return textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html>
        <head>
            <title>Matrix Invitation to {room_name}</title>
            <meta charset="utf-8">
        </head>

        <body>
            <p>You are invited by <b>{inviter_display_name}</b> to join Matrix room <code>{room_name}</code>.</p>
            <p>You will receive an invitation in your Matrix client after you submit
                your <b>Matrix UserID</b> in the box below.</p>
            <p><form method=post>
                <input type=text placeholder="e.g. @rofl:cit.tum.de" name=userid />
                <input type=submit value="Request Invite"/> (This may take some time (~10s))
            </form></p>
            <p>Your Matrix User ID is in the form of <code>@username:servername.tld</code>.
            You can see your ID when pressing on the top left icon in Element!</p>
        </body>
    </html>
    """)
