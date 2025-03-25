from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import nio

from .room import Room, RoomHistoryVisibility
from .room_acl import Role

if TYPE_CHECKING:
    from typing import Any, Iterable

    from .bot import Bot


logger = logging.getLogger(__name__)


class RoomTracker:
    def __init__(self, bot: Bot):
        self._bot = bot
        self._active_rooms: dict[str, Room] = dict()

        # map user_id -> [direct_message_room_id, ...]
        self._dm_mappings: dict[str, list[str]] = dict()

        # map user_id -> {room_id, } ...
        self._user_rooms: dict[str, set[str]] = dict()

    async def init(self, joined_rooms: dict[str, nio.MatrixRoom]):
        """
        recreate all rooms given a list of room ids (e.g. because the matrix server says we're in them).
        this sets up room tracking based on the initial sync.
        """
        for room_id, nio_room in joined_rooms.items():
            room = Room(
                bot=self._bot,
                nio_room=nio_room,
            )

            if await room.setup():
                self.add(room)

                # set up room-user tracking from initial sync state
                for user_id in (await room.get_members()).keys():
                    await self.on_room_join(room_id, user_id)
            else:
                logger.error("failed to initialize room %r in RoomTracker", nio_room)

        # we split setup in two steps: so room plugins can interact!
        logger.info("initialized tracked rooms")
        for room_id, room in self._active_rooms.items():
            logger.info("- %s: mode: %r, name: %s", room_id, room.get_room_mode(), room.display_name)
            await room.init()

        try:
            self._bot.db.write("create temporary table joined_rooms(roomid text unique) strict;")
            self._bot.db.write_many("insert or replace into joined_rooms(roomid) values (?);",
                                    ((k,) for k in joined_rooms.keys()))

            left_rooms = self._bot.db.read(
                "select source_roomid from config_room where source_roomid not in joined_rooms "
                "union "
                "select target_roomid from config_room where target_roomid not in joined_rooms",
            )

            for left_room in left_rooms:
                await self._remove(left_room, removed_by=None)

        finally:
            self._bot.db.write("drop table if exists joined_rooms;")

    def add(self, room: Room):
        if room.room_id in self._active_rooms:
            return
        self._active_rooms[room.room_id] = room

    async def _remove(self, room_id: str, removed_by: str | None) -> None:
        for user_rooms in self._user_rooms.values():
            user_rooms.discard(room_id)

        room = self._active_rooms.pop(room_id, None)
        if room:
            logger.info(f"leaving room {room.room_id}...")
            await room.on_bot_leave(removed_by)
        else:
            logger.info(f"leaving non-active room {room_id}...")

        self._bot.db.write("delete from room_data where roomid=?;", (room_id,))
        self._bot.db.write(
            "delete from config_room where source_roomid=? or target_roomid=?;",
            (room_id, room_id),
        )

        # room is deconstructed here.

    def get(self, room_id: str) -> Room | None:
        return self._active_rooms.get(room_id)

    async def on_room_join(self, room_id: str, user_id: str):
        self._user_rooms.setdefault(user_id, set()).add(room_id)

    async def on_room_leave(self, room_id: str, user_id: str, sender: str) -> None:
        user_rooms = self._user_rooms.get(user_id)
        if user_rooms:
            user_rooms.discard(room_id)

        if user_id == self._bot.user_id:
            await self._remove(room_id, removed_by=sender)

    def update_m_direct(self, m_direct: dict):
        # TODO: when user writes the bot from a room that's not m.direct[user][0]
        # update the bot's m.direct settings so that room gets priority from then on.
        self._dm_mappings = m_direct

    async def is_dm_room(
        self,
        user_id: str,
        room_id: str,
    ) -> bool:
        """
        check if the given room is a direct message room with the given user.
        i.e. just the bot and the user are in it.
        """
        members = {
            member.user_id
            for member in (await self._bot.mxclient.joined_members(room_id)).members
        }
        if len(members) != 2:
            return False

        if members == {user_id, self._bot.user_id}:
            return True

        return False

    async def create_room(
        self,
        creator: str | None = None,
        name: str | None = None,
        topic: str | None = None,
        invite: list[str] = [],
        is_direct: bool = False,
        preset: str | None = None,
        initial_state: list[dict[Any, Any]] = [],
        predecessor: dict[str, Any] | None = None,
        space: bool = False,
        encrypted: bool = False,
        history_visible: RoomHistoryVisibility = RoomHistoryVisibility.invite,
    ) -> Room:
        """
        create a new matrix room with given properties and initial invites.

        is_direct: direct message flag (is_direct) in retrieved m.room.member events
        initial_state: event dicts to submit at room start.
                       the encryption or history_visible events are added before this list.
        encrypted: enable encryption at room start
        invite: [user_id, ...]
        predecessor: {"event_id": "$something:server", "room_id": "!oldroom:server"}

        returns: Room with already-called setup()
        """

        room_preset: nio.RoomPreset | None = {
            "public": nio.RoomPreset.public_chat,   # unencrypted, public join
            "private": nio.RoomPreset.public_chat,  # encrypted, invite only
            "trusted_private": nio.RoomPreset.trusted_private_chat,  # encrypted, invite only, all level 100
        }[preset or "public"]  # default: public

        client = self._bot.mxclient

        initial_state_events = list(initial_state)
        if encrypted:
            initial_state_events.append(
                nio.event_builders.state_events.EnableEncryptionBuilder().as_dict()
            )

        match history_visible:
            case RoomHistoryVisibility.invite:
                initial_state_events.append(
                    nio.event_builders.state_events.ChangeHistoryVisibilityBuilder(
                        visibility="invited",
                    ).as_dict()
                )
            case _:
                raise NotImplementedError()

        create_response = await client.room_create(
            name=name,
            topic=topic,
            invite=invite,
            is_direct=is_direct,
            preset=room_preset,
            initial_state=initial_state_events,
            predecessor=predecessor,
            space=space,
        )
        if isinstance(create_response, nio.RoomCreateError):
            logger.exception("room creation failed")
            raise RuntimeError(f"failed to create matrix room: {create_response}")

        room_id = create_response.room_id

        logger.info(f"Room id={room_id!r} created. Synching...")
        # Wait for the next sync, until the new room is in nio storage and we can send events in the new room
        await client.synced.wait()

        new_room = Room(self._bot, client.rooms[room_id])

        # initial bot configuration
        init_ok = await new_room.setup(invited_by=creator)

        if init_ok:
            self.add(new_room)
        else:
            raise RuntimeError("could not initialize newly joined room")

        return new_room

    async def get_private_room_with_user(
        self,
        user_id: str,
        name: str | None = None,
        topic: str | None = None,
    ) -> Room:
        """
        Finds an existing room with the given user.
        If no room exists a new room is created with only the user and the bot

        TODO: update m_direct when the bot is chatted to from a new DM room by the same user

        @return: the room id of the private room
        """

        m_direct = self._dm_mappings.get(user_id)
        if m_direct:
            # use the first m.direct room
            room = self.get(m_direct[0])
            if room is not None:
                # TODO: probably needs better handling (e.g. removing the m_direct entry)
                return room

        # if we have an exiting room with only user_id and bot.user_id
        if user_rooms := self._user_rooms.get(user_id):
            for room_id in user_rooms:
                if await self.is_dm_room(user_id, room_id):
                    room = self.get(room_id)
                    if not room:
                        raise Exception("inconsistent room tracking")
                    return room

        # Create a new room
        logger.info(f"Creating new private room with {user_id!r}...")

        new_room = await self.create_room(
            is_direct=True,
            preset=nio.RoomPreset.private_chat,
            invite=[user_id],
            encrypted=True,
            history_visible=RoomHistoryVisibility.invite,
        )

        return new_room

    def rooms_from_ids(self, room_ids: Iterable[str]) -> Iterable[Room]:
        for room_id in room_ids:
            room = self.get(room_id)
            if not room:
                raise KeyError(f"unknown room id {room_id!r}")
            yield room

    async def get_create_config_source_rooms(self, for_room: Room, inviter: str, name: str) -> set[Room]:
        if config_rooms := await self.config_source_rooms(for_room.room_id):
            return set(self.rooms_from_ids(config_rooms))

        logger.debug("%s: creating new config room", for_room)
        new_config_room = await self.get_private_room_with_user(user_id=inviter, name=name)

        # the bot can be configured by the inviter only (and bot admins)
        logger.debug("%s: granting config access to inviter %s", for_room, inviter)
        with for_room.acl as acl:
            acl.user_role_add(inviter, Role.config)

        # remember config room for interaction room
        self._bot.db.write(
            "insert or replace into config_room(source_roomid, target_roomid) values (?, ?);",
            (new_config_room.room_id, for_room.room_id),
        )

        return {new_config_room}

    async def config_source_rooms(self, room_id: str) -> set[str]:
        """
        which rooms can configure this the given room
        """
        config_rooms = self._bot.db.read(
            "select source_roomid from config_room where target_roomid=?;",
            (room_id,),
        )
        ret: set[str] = set()
        while True:
            rooms = config_rooms.fetchmany()
            if not rooms:
                break
            ret.update(room[0] for room in rooms)
        return ret

    async def config_target_rooms(self, room_id: str) -> set[str]:
        """
        which rooms does the given room configure?
        """
        configured_rooms = self._bot.db.read(
            "select target_roomid from config_room where source_roomid=?;",
            (room_id,),
        )
        ret: set[str] = set()
        while True:
            rooms = configured_rooms.fetchmany()
            if not rooms:
                break
            ret.update(room[0] for room in rooms)
        return ret

    async def is_config_room(self, room_id: str, config_room_for: str | None = None) -> bool:
        """
        is the given room used to configure other rooms?
        if config_room_for is given, is this room able to configure it?
        """

        if config_room_for:
            has_configroom = self._bot.db.read(
                "select 1 from config_room where target_roomid=? and source_roomid=?;",
                (config_room_for, room_id),
            )
            return has_configroom.fetchone() is not None

        else:
            has_configroom = self._bot.db.read(
                "select 1 from config_room where source_roomid=?;",
                (room_id,),
            )
            return has_configroom.fetchone() is not None
