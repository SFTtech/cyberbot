from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import nio

from .database import Database
from .room import Room, RoomHistoryVisibility

if TYPE_CHECKING:
    from .bot import Bot


logger = logging.getLogger(__name__)


class RoomTracker:
    def __init__(self, bot: Bot, db: Database):
        self._bot = bot
        self._db = db
        self._active_rooms: dict[str, Room] = dict()

        # map user_id -> [direct_message_room_id, ...]
        self._dm_mappings: dict[str, list[str]] = dict()

        # map user_id -> {room_id, } ...
        self._user_rooms: dict[str, set[str]] = dict()

    async def init(self, joined_rooms: dict[str, nio.MatrixRoom]):
        """
        recreate all rooms given a list of room ids (e.g. because the matrix server says we're in them).
        """
        for room_id, nio_room in joined_rooms.items():
            room = Room(
                bot=self._bot,
                nio_room=nio_room,
            )

            if await room.setup():
                self.add(room)

                # set up initial room-user tracking
                for user_id in (await room.get_members()).keys():
                    await self.on_room_join(room_id, user_id)
            else:
                logger.error("failed to initialize room %r in RoomTracker", nio_room)

        # we split setup in two steps: so room plugins can interact!
        logger.info("initialized tracked rooms")
        for room_id, room in self._active_rooms.items():
            logger.info("- %s: mode: %r, name: %s", room_id, room.get_room_mode(), room.display_name)
            await room.init()

        # TODO self._cleanup() to remove db-content for unknown rooms.

    def add(self, room: Room):
        if room.room_id in self._active_rooms:
            return

        self._active_rooms[room.room_id] = room

    async def _remove(self, room_id: str, removed_by: str) -> None:
        for user_rooms in self._user_rooms.values():
            user_rooms.discard(room_id)

        room = self._active_rooms.pop(room_id, None)
        if room:
            await room.on_bot_leave(removed_by)
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
        for room_id, room in self._active_rooms.items():
            member = room.get_member(user_id)
            if member is not None:
                # TODO: maybe allow multi-user config rooms someday
                if await self.is_dm_room(user_id, room_id):
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
