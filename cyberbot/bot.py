from __future__ import annotations

import asyncio
import logging
import socket
import time
import traceback
from typing import Any

import nio
from nio.events.account_data import AccountDataEvent, UnknownAccountDataEvent
from nio.events.invite_events import InviteMemberEvent
from nio.events.room_events import RoomMemberEvent, RoomMessageFormatted, RoomMessageNotice, RoomMessageText

from .api.room_plugin import RoomPlugin
from .api.service import Service
from .config import Config
from .database import Database
from .module_loader import load_modules
from .room import Room
from .room_tracker import RoomTracker
from .service import github, gitlab, http_server, invite_manager

logger = logging.getLogger(__name__)


class Bot:
    def __init__(self, config: Config):
        self._config = config

        self._db = Database(config.storage.database_path)
        self._own_user_id = config.matrix.user

        client_config = nio.AsyncClientConfig(store_sync_tokens=False)
        self._client = nio.AsyncClient(
            homeserver=config.matrix.homeserver,
            user=self._own_user_id,
            device_id=config.matrix.deviceid,
            store_path=str(config.storage.cryptostate_path),
            config=client_config,
        )

        self._password = config.matrix.password
        self.botname = config.bot.name

        self._allowed_rooms = config.bot.rooms_allowed
        # validate matrix room syntax
        for room in self._allowed_rooms:
            if not (room.startswith("!") or ":" in room):
                raise ValueError(
                    f"invalid allowed room. it must start with '!' and contain ':' -> {room!r}"
                )
        self.rooms = RoomTracker(self, self._db)

        self._last_sync_time = 0.0
        self._available_plugins: dict[str, type[RoomPlugin]] = dict()

        self._event_tasks: set[asyncio.Task] = set()

        # TODO maybe allow selective disabling.
        # the module can depend on another when .setup() is called in _start_services()
        self._services: dict[str, Service] = {
            "http_server": http_server.HTTPServer(self),
            "gitlab_hook_server": gitlab.GitLabServer(self),
            "github_hook_server": github.GitHubServer(self),
            "invite_manager": invite_manager.InviteManager(self),
        }

    def get_plugins(self) -> dict[str, type[RoomPlugin]]:
        return self._available_plugins

    def get_service(self, name: str) -> Service:
        if service := self._services.get(name):
            return service
        raise KeyError(f"service {name} not known")

    def get_config(self, module_name: str) -> dict[str, Any] | None:
        return self._config.config.get(module_name)

    def is_admin(self, user_id: str) -> bool:
        return user_id in self._config.bot.admins

    @property
    def db(self) -> Database:
        return self._db

    @property
    def mxclient(self) -> nio.AsyncClient:
        return self._client

    @property
    def user_id(self) -> str:
        return self._own_user_id

    async def _start_services(self):
        logger.info("starting global plugins...")
        for service in self._services.values():
            await service.setup()
            await service.start()

    async def _initial_sync(self, test=False):
        # fetch room list and everything else for the current matrix state
        # this also skips all past messages before we start handling them them.
        # otherwise we'd reprocess the whole past.
        # see "Synching" in the matrix client-server spec.
        sync_resp = await self._client.sync(since=None)
        self._last_sync_time = time.time()

        if isinstance(sync_resp, nio.SyncError):
            if test:
                return False
            raise RuntimeError(f"error for initial sync: {sync_resp}")
        elif isinstance(sync_resp, nio.SyncResponse):
            pass
        else:
            raise RuntimeError(f"unknown sync response: {sync_resp}")
        return True

    async def _login(self):
        logger.info("logging into Matrix...")

        access_token_checked = False

        login_props_raw = self._db.read(
            "select key, value from state where key in "
            "('login_user_id', 'login_token', 'login_device_id')"
        ).fetchall()

        if login_props_raw:
            login_props = dict(login_props_raw)
            # reuse previous login token
            token = login_props.get("login_token")

            if token:
                user_id = login_props.get("login_user_id")
                if user_id != self._client.user:
                    # TODO what to do? ask to logout?
                    raise Exception(
                        f"stored logged in user ({user_id!r}) does not match config ({self._client.user!r}) "
                    )

                device_id = login_props.get("login_device_id")
                if device_id != self._client.device_id:
                    logger.warning(
                        f"cached device id ({device_id!r}) of the current login token "
                        f"does not match bot configuration file ({self._client.device_id!r}). "
                        "using the cached one to proceed - please re-login or update the config file."
                    )

                logger.debug("reusing stored access_token...")

                self._client.restore_login(
                    user_id=user_id,
                    device_id=device_id,
                    access_token=token,
                )

                access_token_checked = await self._whoami(test=True)

        if not access_token_checked:
            # do a new password login, obtain a new token
            # TODO: update device name on start?
            name = f"{self.botname} on {socket.gethostname()}"
            response = await self._client.login(
                password=self._password, device_name=name
            )

            if isinstance(response, nio.LoginError):
                raise RuntimeError(f"Error logging in: {response}")
            elif isinstance(response, nio.LoginResponse):
                # persist the new access token
                self._db.write_many(
                    "insert or replace into state(key, value) values (?, ?)",
                    [
                        ("login_user_id", response.user_id),
                        ("login_token", response.access_token),
                        ("login_device_id", response.device_id),
                    ],
                )
            else:
                raise RuntimeError(f"unknown login response: {response!r}")

        if not access_token_checked:
            await self._whoami()

        if self._client.should_upload_keys:
            await self._client.keys_upload()

        await self._initial_sync()

        await self._check_devices()
        await self._update_displayname()

    async def _check_devices(self):
        """
        maintain the bot's device list
        """

        devices_resp = await self._client.devices()
        if isinstance(devices_resp, nio.DevicesResponse):
            logger.info("current devices:")
            for idx, device in enumerate(devices_resp.devices):
                logger.info(
                    "%d: %s: %s (seen %s at %s)",
                    idx,
                    device.id,
                    device.display_name,
                    device.last_seen_ip,
                    device.last_seen_date,
                )
        else:
            logger.warning(f"failed to get current devices: {devices_resp}")

    async def _whoami(self, test=False):
        """
        fetch our real user id.
        when this is performed by nio, nio also updates its user/deviceid internally.
        """
        whoami_resp = await self._client.whoami()

        if isinstance(whoami_resp, nio.WhoamiResponse):
            self._own_user_id = whoami_resp.user_id
            self._own_device_id = whoami_resp.device_id

        elif isinstance(whoami_resp, nio.WhoamiError):
            if test:  # todo: test if whoami_resp is a bad login?
                return False
            raise RuntimeError(f"failed whoami: {whoami_resp!r}")

        else:
            raise RuntimeError(f"unknown whoami response: {whoami_resp!r}")

        return True

    async def __aenter__(self):
        self._db.migrate()
        try:
            await self._login()
        except Exception:
            await self._client.close()
            raise

        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        await self._client.close()

    async def _load_rooms(self):
        logger.info("Loading rooms...")

        # the joined room response in nio populates self._client.rooms.
        await self._client.joined_rooms()
        await self.rooms.init(self._client.rooms)

    async def _load_modules(self):
        logger.debug("loading room modules...")
        modules = load_modules(self._config.load_modules)

        for module_name, module in modules.items():
            module_cls: type[RoomPlugin] = module.Module
            if not isinstance(module_cls, type(RoomPlugin)):
                raise Exception(f"module.Module {module_name!r} is not a RoomPlugin subclass, it's {module_cls}")
            self._available_plugins[module_name] = module_cls

    async def _update_displayname(self):
        """
        sync the configured displayname
        """
        displayname_resp = await self._client.get_displayname()
        if isinstance(displayname_resp, nio.ProfileGetDisplayNameResponse):
            cur_displayname = displayname_resp.displayname
            if cur_displayname != self.botname:
                logger.info(f"Changing bot displayname to {self.botname!r}")
                await self._client.set_displayname(self.botname)
        else:
            logger.warning(f"failed to get current display name: {displayname_resp}")

    def in_room(self, room_id: str) -> bool:
        """
        check if the bot currently is in the given room id.
        needed for cross-room available check during our Room initialization.
        """
        if self._client.rooms.get(room_id) is not None:
            return True
        return False

    def _bot_invite_allowed(self, inviter: str, room: nio.MatrixRoom) -> bool:
        """
        possible bot invite flows:
        - a bot admin invites to any room
        - bot is invited to whitelisted room

        future: per-user configuration rooms?
        """

        if inviter in self._config.bot.admins:
            # inviter is an admin
            return True

        if self._allowed_rooms:
            if room.room_id not in self._allowed_rooms:
                return False
        else:
            return True

        return False

    async def _handle_room_invite(self, room: nio.MatrixInvitedRoom):
        inviter = room.inviter

        if not self._bot_invite_allowed(inviter, room):
            logger.info(f"Rejecting invite to room {room.room_id} invited by {inviter}")
            await self._client.room_leave(room.room_id)
            return

        if room.room_id not in self._client.rooms:
            logger.info(f"Joining room {room.room_id}...")
            response = await self._client.join(room.room_id)
            if isinstance(response, nio.responses.JoinResponse):
                new_room = Room(self, room)

                init_ok = await new_room.setup(invited_by=inviter)
                if init_ok:
                    self.rooms.add(new_room)

            else:
                logger.warning(f"Couldn't joing the room: {response!r}")
        else:
            logger.warning(f"Not joining room {room.room_id!r}. We're already joined.")

    async def _on_invite_event(self, room: nio.MatrixRoom, event: InviteMemberEvent):
        """
        triggered when the bot is invited to a room.
        can be a DM or a group chat.
        """

        # filter for invites for us only
        if event.membership != "invite" or event.state_key != self._own_user_id:
            return

        # nio tracks the room invitations on its own
        # and constructs the MatrixInvitedRoom from that
        invited_room = self._client.invited_rooms[room.room_id]
        await self._handle_room_invite(invited_room)

    async def _on_room_member_event(
        self, nio_room: nio.MatrixRoom, event: RoomMemberEvent
    ) -> None:

        who = event.state_key
        sender = event.sender

        match event.membership:
            case "join":
                await self.rooms.on_room_join(nio_room.room_id, who)
            case "leave" | "ban": # incl. kick
                await self.rooms.on_room_leave(nio_room.room_id, who, sender)
            case "knock":
                # TODO: automatic room knock accepting?
                pass
            case _:
                pass

    async def _on_text_event(
        self, nio_room: nio.MatrixRoom, event: RoomMessageFormatted
    ):
        # we ignore messages older than 5secs before last sync to solve
        # joining new room and interpreting old messages problem
        if (self._last_sync_time - 5) * 1000 > event.server_timestamp:
            logger.debug(f"Ignoring old event in room {nio_room.room_id}")
            return

        if event.sender == self._client.user:
            # ignore own message in room
            return

        room = self.rooms.get(nio_room.room_id)
        if room is not None:
            try:
                # delivery to each plugin in the room
                await room.on_text_event(event)

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception(f"failed text handling in room {room.room_id}")
                show_exception_in_room = False
                # TODO show it in config room?
                if show_exception_in_room:
                    try:
                        tb = traceback.format_exc()
                        msg = f"failed to handle text event in room:\n{tb}"
                        # TODO: format as source block
                        await room.send_text(msg)
                    except Exception:
                        logger.exception("failed sending text handle failure exception")
        else:
            logger.info(f"Ignoring text event in non-active room {nio_room.room_id}")

    async def _on_event(self, room, event):
        async def event_task(room, event):
            try:
                # every task must be handled in 60s
                await asyncio.wait_for(self._process_event(room, event), 60)
            except TimeoutError:
                logger.debug(
                    "room %s event %s took longer than 60s", room.room_id, type(event)
                )
            except Exception:
                logger.exception("room %s event %s failed", room.room_id, type(event))

        task = asyncio.create_task(event_task(room, event))

        def event_handled(fut):
            fut.result()  # retrieve event handling exceptions
            self._event_tasks.discard(fut)

        task.add_done_callback(event_handled)
        self._event_tasks.add(task)

    async def _process_event(self, room, event):
        match event:
            case InviteMemberEvent():
                await self._on_invite_event(room, event)

            case RoomMessageText() | RoomMessageNotice():
                await self._on_text_event(room, event)

            case RoomMemberEvent():
                await self._on_room_member_event(room, event)

            case nio.MegolmEvent():
                # "MegolmEvents are presented to library users only if the library fails
                # to decrypt the event because of a missing session key."
                #
                # TODO: validate if we need to implement this
                #       or nio does it on its own in the current release.
                logger.warn(f"Unable to decrypt event {event}, requesting room keys...")
                logger.debug(
                    f"OLM account is shared: {self._client.olm_account_shared!r}"
                )
                logger.debug(f"Event session ID: {event.session_id!r}")

                # clear pending key request, send a new one
                r = nio.crypto.OutgoingKeyRequest(event.session_id, None, None, None)
                self._client.store.remove_outgoing_key_request(r)
                self._client.olm.outgoing_key_requests.pop(event.session_id, None)

                await self._client.request_room_key(event)

            case nio.ReactionEvent():
                pass
            case nio.RedactionEvent():
                pass

            case _:
                logger.debug(f"Ignoring unhandled event: {event!r}")

    async def _on_todevice(self, request):
        logger.debug(f"to device event: {request!r}")

    async def _on_ephemeral_event(self, arg1, arg2):
        logger.debug(f"ephemeral event: {arg1!r} {arg2!r}")

    async def _on_global_account_data(self, event: AccountDataEvent):
        # when there's a dedicated m.direct account data event, we need to update our cache.
        if isinstance(event, UnknownAccountDataEvent):
            if event.type == "m.direct":
                self.rooms.update_m_direct(event.content)

    async def _on_kick_response(self, response):
        logger.info(f"kick response: {response!r}")

    async def _on_response(self, response):
        self._last_sync_time = time.time()

    async def _listen(self):
        logger.debug("setting up matrix event callbacks...")
        # InviteMemberEvent is not a room-event ("Event"), since its not in a active Room yet.
        self._client.add_event_callback(self._on_event, InviteMemberEvent)

        self._client.add_event_callback(self._on_event, nio.Event)

        # self._client.add_to_device_callback(
        #     self._on_todevice, nio.events.to_device.ToDeviceEvent
        # )
        # self._client.add_ephemeral_callback(
        #     self._on_ephemeral_event, nio.events.ephemeral.EphemeralEvent
        # )
        # self._client.add_response_callback(self._on_kick_response, nio.RoomKickResponse)

        self._client.add_response_callback(self._on_response, nio.Response)
        self._client.add_room_account_data_callback(
            self._on_global_account_data, nio.Response
        )

        logger.info(f"{self.botname} ready for action!")

        # process pending room invites
        for invited_room in self._client.invited_rooms.values():
            await self._handle_room_invite(invited_room)

        # process all new events
        await self._client.sync_forever()

    async def run(self):
        await self._load_modules()
        await self._start_services()
        await self._load_rooms()
        await self._listen()
