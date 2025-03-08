from __future__ import annotations

import enum
import io
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import imagesize
import nio

from .room_acl import Role, RoomACL
from .room_module import RoomModule
from .types import Err, Ok, Result
from .util import run_tasks

if TYPE_CHECKING:
    from .api.room_plugin import RoomPlugin
    from .bot import Bot, RoomMessageText


class RoomMode(enum.IntFlag):
    """
    configuration and plugin interaction are separate in rooms.
    a room can be used for plugin io or configuration of other room(s).
    """

    DISABLED = 0

    # bot plugins are active
    INTERACTION = 1 << 0

    # config plugin is active
    CONFIG = 1 << 1


class RoomHistoryVisibility(enum.Enum):
    """
    how history can be viewed by room members
    """

    # starting at the point they were invited
    invite = enum.auto()


class Room:
    def __init__(self, bot: Bot, nio_room: nio.MatrixRoom):
        self.room_id = nio_room.room_id

        self._bot = bot
        self._nio_room = nio_room
        self._modules: dict[str, RoomModule] = dict()
        self._log = logging.getLogger(f"{__name__}.{self.room_id}")

        self._acl = RoomACL(bot, self.room_id)

    def __str__(self):
        return f"Matrix Room {self.room_id}{' encrypted' if self._nio_room.encrypted else ''}"



    def get_room_mode(self) -> RoomMode | None:
        room_mode_row = self._bot.db.read(
            "select value from room_data where roomid=? and key=?",
            (self.room_id, "room_mode"),
        ).fetchone()

        if room_mode_row is None:
            return None

        return RoomMode(int(room_mode_row[0]))

    async def setup(
        self,
        invited_by: str | None = None,
        config_room_for: str | None = None,
    ) -> bool:
        """
        when the room is created upon initial join or bot restart.

        for each managed room, link to its config room(s):

        TODO future:
        - one shared configroom: all users with privileges are joined

        returns if initialization succeeded
        """

        # do we know this room already?
        room_mode = self.get_room_mode()

        if room_mode is None:
            room_mode, ok = await self._setup_new(
                invited_by=invited_by, config_room_for=config_room_for
            )
            if not ok:
                self._log.warning("failed to setup new room")
                return False

        elif room_mode == RoomMode.DISABLED:
            self._log.warning("skipping initialization of disabled room")
            return False

        # this room can be used to configure another room
        if RoomMode.CONFIG in room_mode:
            configured_rooms = await self.config_target_rooms()

            # cleanup rooms we're no longer in
            obsolete_tgt_rooms: set[str] = set()
            for room_id in configured_rooms:
                if not self._bot.in_room(room_id):
                    obsolete_tgt_rooms.add(room_id)

            if obsolete_tgt_rooms:
                self._log.info("removing config target rooms: %s", obsolete_tgt_rooms)
                self._bot.db.write_many("delete from config_room where source_roomid=? and target_roomid=?;",
                                        paramlist=((self.room_id, obsolete) for obsolete in obsolete_tgt_rooms))

            ok = await self._load_plugin("config")
            if not ok:
                self._log.warning("failed to load config plugin")
                return False

        # this room can be configured by a config room and has interaction plugins
        if RoomMode.INTERACTION in room_mode:
            # which room can configure this room?
            config_rooms = await self.config_source_rooms()

            # cleanup config rooms we're no longer in
            obsolete_src_rooms: set[str] = set()
            for room_id in config_rooms:
                if not self._bot.in_room(room_id):
                    obsolete_src_rooms.add(room_id)

            if obsolete_src_rooms:
                self._log.info("removing config source rooms: %s", obsolete_src_rooms)
                self._bot.db.write_many("delete from config_room where source_roomid=? and target_roomid=?;",
                                        paramlist=((obsolete, self.room_id) for obsolete in obsolete_src_rooms))

            # load configured plugins for the room
            # assume it's ok if they fail, recovery should be done from the config room then.
            await self._load_plugins()

        return True

    async def init(self) -> None:
        for plugin in self._modules.values():
            await plugin.init()

    async def config_target_rooms(self) -> set[str]:
        """
        which rooms does this room configure?
        """
        configured_rooms = self._bot.db.read(
            "select target_roomid from config_room where source_roomid=?;",
            (self.room_id,),
        )
        ret: set[str] = set()
        while True:
            rooms = configured_rooms.fetchmany()
            if not rooms:
                break
            ret.update(room[0] for room in rooms)
        return ret

    async def config_source_rooms(self) -> set[str]:
        """
        which rooms can configure this room?
        """
        config_rooms = self._bot.db.read(
            "select source_roomid from config_room where target_roomid=?;",
            (self.room_id,),
        )
        ret: set[str] = set()
        while True:
            rooms = config_rooms.fetchmany()
            if not rooms:
                break
            ret.update(room[0] for room in rooms)
        return ret

    async def is_config_room(self, config_room_for: str | None = None) -> bool:
        """
        is this room used to configure other rooms?
        if config_room_for is given, is this room able to configure it?
        """

        if config_room_for:
            has_configroom = self._bot.db.read(
                "select 1 from config_room where target_roomid=? and source_roomid=?;",
                (config_room_for, self.room_id),
            )
            return has_configroom.fetchone() is not None

        else:
            has_configroom = self._bot.db.read(
                "select 1 from config_room where source_roomid=?;",
                (self.room_id,),
            )
            return has_configroom.fetchone() is not None

    async def _setup_new(
        self, invited_by: str | None = None, config_room_for: str | None = None
    ) -> tuple[RoomMode, bool]:

        # we didn't see this room before.
        room_mode = RoomMode.DISABLED

        inviter_candidates = (await self.get_members()).keys() - {self._bot.user_id}
        if config_room_for is not None or len(inviter_candidates) == 1:
            # we end up here due to the private room creation below.
            # or because it's a lonely bot-user direct room.
            #
            # let's treat this as a new configuration room.

            self._log.debug("registering as new config room")
            room_mode |= RoomMode.CONFIG

            if config_room_for:
                self._bot.db.write(
                    "insert or replace into config_room(source_roomid, target_roomid) values (?, ?);",
                    (self.room_id, config_room_for),
                )

        else:
            # it's a new room with other people
            self._log.debug("registering as new interaction room")
            room_mode |= RoomMode.INTERACTION

            if invited_by is None:
                self._log.error(
                    "no known inviter for initial room join - can't grant access to them"
                )
                return room_mode, False

            if invited_by:
                self._log.debug("granting config access to inviter %s", invited_by)

                # the bot can be configured by the inviter only (and bot admins)
                with self._acl as acl:
                    acl.user_role_add(invited_by, Role.config)

                # create or fetch a `Room` for configuration
                self._log.debug("fetch or create bot configuration room...")
                config_room = await self._bot.rooms.get_private_room_with_user(
                    invited_by,
                    name=f"{self._bot.botname} config",
                )

                # remember config room for interaction room
                self._bot.db.write(
                    "insert or replace into config_room(source_roomid, target_roomid) values (?, ?);",
                    (config_room.room_id, self.room_id),
                )

                # TODO: use RoomAPI to send&format once available
                await config_room.send_text(html=(f'I just joined room "{self.display_name}" '
                                                  f'(<code>{self.room_id}</code>) '
                                                  f'by invite from {invited_by}'), notice=True)

        # record discovered room mode
        self._bot.db.write(
            "insert or replace into room_data(roomid, key, value) values(?, ?, ?);",
            (self.room_id, "room_mode", room_mode),
        )

        return room_mode, True

    async def _load_plugin(self, pluginname: str) -> bool:
        plugin = RoomModule(self._bot, self, pluginname)

        ok = await plugin.load()
        if ok:
            self._modules[pluginname] = plugin

        return ok

    async def _load_plugins(self):
        self._log.info("Loading enabled room plugins...")
        rows = self._bot.db.write(
            "select pluginname from room_plugins where roomid = ?;",
            (self.room_id,),
        )

        for (pname,) in rows.fetchall():
            ok = await self._load_plugin(pname)
            if isinstance(ok, Err):
                self._log.error(f"failed to load plugin {pname}")

    async def activate_plugin(self, pluginname: str) -> Result[str, str]:
        if pluginname in self._modules:
            return Ok("is already loaded")

        self._log.info(f"Adding plugin {pluginname}...")
        if pluginname not in self._bot.get_plugins():
            self._log.warning(f"tried to load invalid plugin {pluginname}")
            return Err(f"Plugin '{pluginname}' does not exists")

        self._log.info(f"Loading plugin {pluginname}...")
        ok = await self._load_plugin(pluginname)
        if ok:
            await self._modules[pluginname].init()
            self._bot.db.write(
                """
                insert into room_plugins(roomid, pluginname)
                values (?,?);
                """,
                (self.room_id, pluginname),
            )

            return Ok(f"loaded {pluginname}")
        else:
            return Err(f"Failed to activate plugin '{pluginname}', see server log!")

    async def remove_plugin(self, pluginname) -> Result[str, str]:
        self._log.info(f"Removing plugin {pluginname} from room...")

        # make sure the plugin won't load at next bot startup
        self._bot.db.write(
            """
            delete from room_plugins
            where roomid=? and pluginname=?;
            """,
            (self.room_id, pluginname),
        )

        module = self._modules.pop(pluginname, None)
        if module is not None:
            await module.destroy()

        self._log.info(f"plugin {pluginname} removed.")
        return Ok(f"plugin '{pluginname}' removed")

    def get_plugins(self) -> dict[str, RoomPlugin]:
        return {
            plugin_name: module.plugin
            for plugin_name, module in self._modules.items()
        }

    @property
    def acl(self) -> RoomACL:
        return self._acl

    @property
    def encrypted(self):
        return self._nio_room.encrypted

    @property
    def display_name(self):
        return self._nio_room.display_name

    @property
    def member_count(self):
        return self._nio_room.member_count

    async def get_members(self) -> dict[str, nio.MatrixUser]:
        """
        TODO: better rely on nio's room member tracking?
        """
        members = (await self._bot.mxclient.joined_members(self.room_id)).members
        ret: dict[str, nio.MatrixUser] = dict()
        for member in members:
            ret[member.user_id] = member
        return ret

    def get_member(self, user_id: str) -> nio.MatrixUser | None:
        return self._nio_room.users.get(user_id)

    async def on_bot_leave(self, removed_by: str) -> None:
        await run_tasks([
            p.destroy()
            for p in self._modules.values()
        ], timeout=5)

    async def on_text_event(self, event: RoomMessageText) -> None:
        await run_tasks([
            p.on_text_message(event)
            for p in self._modules.values()
        ], timeout=20)

    ### functions for adding room content
    async def send_message(
        self, content: dict[Any, Any]
    ) -> nio.RoomSendResponse | nio.RoomSendError:
        return await self._bot.mxclient.room_send(
            room_id=self.room_id,
            message_type="m.room.message",
            content=content,
            ignore_unverified_devices=True,
        )

    async def send_text(
        self, text: str | None = None, html: str | None = None, notice: bool = False
    ):
        content: dict[str, str]
        if html is not None:
            content = {
                "msgtype": "m.notice" if notice else "m.text",
                "body": text or "",  # maybe strip all tags from html text
                "formatted_body": html,
                "format": "org.matrix.custom.html",
            }
        elif text is not None:
            content = {
                "msgtype": "m.notice" if notice else "m.text",
                "body": text,
            }
        else:
            raise ValueError("no message content given")

        return await self.send_message(
            content=content,
        )

    async def send_html(self, html: str, text: str = "", notice=False):
        return await self.send_text(html=html, text=text, notice=notice)

    async def send_image(self, handle: io.BytesIO, filename: str):
        iostart = handle.tell()

        # analyse the image
        try:
            width, height = imagesize.get(handle)
        except ValueError:
            self._log.exception("failed to send image")
            return

        filepath = Path(filename)
        extension = filepath.suffix.lower()[1:]
        mime = f"image/{extension.replace('jpeg', 'jpg')}"

        ioend = handle.seek(0, os.SEEK_END)
        iosize = ioend - iostart

        def get_data_stream(too_many_reqs, timeouts):
            # this function is called again for every upload retry.
            handle.seek(iostart)
            return handle

        # upload the image
        uresp, file_decryption_info = await self._bot.mxclient.upload(
            get_data_stream,
            content_type=mime,
            filename=filepath.name,
            filesize=iosize,
            encrypt=self.encrypted,
        )

        if isinstance(uresp, nio.UploadError):
            self._log.warning(f"Failed to upload image: {uresp.message}")
            return

        uri = uresp.content_uri
        content = {
            "msgtype": "m.image",
            "body": handle.name,
            "url": uri,
            "info": {
                "mimetype": mime,
                "h": height,
                "w": width,
                "size": iosize,
            },
        }

        if self.encrypted and file_decryption_info:
            content["file"] = file_decryption_info
            content["file"]["url"] = uri

        return await self.send_message(content=content)

    async def invite(self, user_id: str) -> Result[None, str]:
        response = await self._bot.mxclient.room_invite(self.room_id, user_id)
        if isinstance(response, nio.RoomInviteResponse):
            return Ok(None)
        else:
            return Err(str(response))

    async def set_name(self, name: str):
        # topic has implementation in nio, but not name?
        return await self._bot.mxclient.room_put_state(
            self.room_id,
            event_type="m.room.name",
            content={"name": name},
        )

    async def set_topic(
        self, topic: str
    ) -> None | nio.RoomPutStateResponse | nio.RoomPutStateError:
        if self._nio_room.topic == topic:
            return None

        return await self._bot.mxclient.update_room_topic(self.room_id, topic)

    def user_name(self, user_id: str) -> str | None:
        """
        get the user display name by user id in this room
        """
        return self._nio_room.user_name(user_id)

    async def get_user_power_level(self, user_id: str) -> int:
        power_levels = await self._bot.mxclient.room_get_state_event(self.room_id, "m.room.power_levels")
        if isinstance(power_levels, nio.RoomGetStateEventError):
            raise ValueError(f"failed to fetch room power levels: {power_levels}")

        user_power_level: int
        try:
            user_power_level = power_levels.content["users"][user_id]
        except KeyError:
            try:
                user_power_level = power_levels.content["users_default"]
            except KeyError as exc:
                raise ValueError("couldn't get user power levels") from exc

        return user_power_level

    async def is_dm_room(self, user_id: str) -> bool:
        return await self._bot.rooms.is_dm_room(user_id, self.room_id)
