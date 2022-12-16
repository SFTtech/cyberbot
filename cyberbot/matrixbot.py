import asyncio
import sys
import os
import time
import importlib
import logging
import traceback
import sqlite3
import sys

from pathlib import Path
from pprint import pprint

from matrixroom import MatrixRoom
from plugin import Plugin

import nio

DEFAULT_BOTNAME = "Matrix Bot"
DEFAULT_PLUGINPATH = ["./plugins"]
DEFAULT_DEVICEID = "MATRIXBOT"
DEFAULT_DBPATH = "./matrixbot.sqlite"
DEFAULT_BIND_ADDRESS = "localhost"
DEFAULT_BIND_PORT = "8080"
DEFAULT_GLOBAL_PLUGINPATH = "./global_plugins"

logger = logging.getLogger(__name__)


class MatrixBot:
    def __init__(self, config):
        self.config = config

        if not "BotMatrixId" in config or not all(
            key in config["BotMatrixId"] for key in ["USERNAME", "PASSWORD", "SERVER"]
        ):
            sys.stderr.write(
                """Bad config file. Please check that config file exists and all fields are available\n"""
            )
            sys.exit(-1)
        botc = config["BotMatrixId"]

        store_path = botc.get("STOREPATH", "")

        if not store_path:
            store_path = Path(os.getcwd()) / "store"
        else:
            store_path = Path(store_path)

        if not store_path.is_dir():
            logger.info(f"Creating store directory in {store_path}")
            try:
                os.mkdir(store_path)
            except Exception as e:
                logger.error("Failed to create store path. Check permissions.")
                print(e)
                sys.exit(-1)

        logger.info(f"Store path: {store_path}")

        self.client = nio.AsyncClient(
            botc["SERVER"],
            botc["USERNAME"],
            device_id=botc.get("DEVICEID", DEFAULT_DEVICEID),
            store_path=str(store_path),
        )

        self.password = botc["PASSWORD"]
        self.botname = botc.get("BOTNAME", DEFAULT_BOTNAME)

        self.dbpath = botc.get("DBPATH", DEFAULT_DBPATH)
        self.load_db(self.dbpath)
        self.pluginpath = [
            p.strip() for p in botc.get("PLUGINPATH", DEFAULT_PLUGINPATH).split(";")
        ]
        self.environment = dict(
            (k.upper(), v) for k, v in dict(botc).items() if k.lower() != "password"
        )
        self.last_sync_time = 0

        self.active_rooms = set()
        self.available_plugins = {}
        # order of global_plugins is important as they may depend on each other
        # also the non-global plugins may depend on them
        # thus we map by index between names and plugins and do not use a dict()
        self.global_pluginpath = botc.get(
            "GLOBAL_PLUGINPATH", DEFAULT_GLOBAL_PLUGINPATH
        )
        self.global_plugin_names = [
            p.strip() for p in botc.get("GLOBAL_PLUGINS", "").split(";")
        ]
        self.global_plugins = [None] * len(self.global_plugin_names)

        # this is a small hack to add the plugins to the import search path
        for path in self.pluginpath:
            sys.path.append(path)
        sys.path.append(self.global_pluginpath)

        self.allowed_rooms = [
            r for r in botc.get("ROOM_WHITE_LIST", "").split(";") if r != ""
        ]

    def get_global_plugin_object(self, name):
        i = self.global_plugin_names.index(name)
        return self.global_plugins[i].Object

    async def start_global_plugins(self):
        logger.info("Starting global plugins")
        for i in range(len(self.global_plugin_names)):
            # it's the plugin's job to set up that this works
            await self.global_plugins[i].Object.set_bot(self)
            await self.global_plugins[i].Object.start()

    async def login(self):
        import socket

        logger.info("Logging Bot in")
        hname = socket.gethostname()
        response = await self.client.login(self.password, device_name=hname)
        if type(response) == nio.LoginError:
            logger.error(
                "There was an error while logging in. Please check credentials"
            )
            sys.exit(-1)
        k = await self.client.sync()  # otherwise all past messages will be handled
        self.last_sync_time = time.time()
        if self.client.should_upload_keys:
            await self.client.keys_upload()
        cur_displayname = (await self.client.get_displayname()).displayname
        logger.info(f"Current displayname: {cur_displayname}")
        if cur_displayname != self.botname:
            logger.info(f"Changing displayname to {self.botname}")
            await self.client.set_displayname(self.botname)

    async def __aenter__(self):
        await self.login()
        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        await self.client.close()

    def load_db(self, dbname):
        logger.info(f"Opening Database {dbname}")
        self.conn = sqlite3.connect(dbname)
        c = self.conn.cursor()
        tables = c.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type ='table' AND name NOT LIKE 'sqlite_%';
            """
        ).fetchall()
        # attention here, meaning of "plugin_data" has changed
        # room_data: global room data
        # plugin_data: global plugin data
        # room_plugin_data: data local to a plugin x room combination
        # room_plugins: which plugins are loaded in which room
        if not all(
            (t,) in tables
            for t in [
                "rooms",
                "plugins",
                "room_plugins",
                "room_data",
                "plugin_data",
                "room_plugin_data",
            ]
        ):
            c.execute(
                """
                CREATE TABLE rooms (
                    roomid     VARCHAR PRIMARY KEY
                );
                """
            )
            c.execute(
                """
                CREATE TABLE plugins (
                    pluginname VARCHAR PRIMARY KEY
                );
                """
            )
            c.execute(
                """
                CREATE TABLE room_plugins (
                    roomid     VARCHAR,
                    pluginname VARCHAR,
                    PRIMARY KEY (roomid, pluginname)
                );
                """
            )
            c.execute(
                """
                CREATE TABLE room_data (
                    roomid     VARCHAR,
                    key        VARCHAR,
                    value      TEXT,
                    PRIMARY KEY (roomid, key)
                );
                """
            )
            c.execute(
                """
                CREATE TABLE plugin_data (
                    pluginname VARCHAR,
                    key        VARCHAR,
                    value      TEXT,
                    PRIMARY KEY (pluginname, key)
                );
                """
            )
            c.execute(
                """
                CREATE TABLE room_plugin_data (
                    roomid     VARCHAR,
                    pluginname VARCHAR,
                    key        VARCHAR,
                    value      TEXT,
                    PRIMARY KEY (roomid, pluginname, key)
                );
                """
            )

    async def load_rooms(self):
        logger.info("Loading Roomns")
        joined_rooms = self.client.rooms
        cursor = self.conn.cursor()
        res = cursor.execute(
            """
            SELECT *
            FROM rooms;
            """
        )
        dbrooms = res.fetchall()
        for rid, nio_room in joined_rooms.items():
            # self.allowed_rooms is ignored, because bernd can create rooms by himself
            if (rid,) in dbrooms:
                mr = MatrixRoom(
                    matrixbot=self,
                    nio_room=nio_room,
                )
                await mr.load_plugins()
                self.active_rooms.add(mr)

    async def read_plugins(self):
        plugin_paths = [Path(path) for path in self.pluginpath]
        logger.info(f"Reading available plugins from: {plugin_paths}")

        help_module = None

        for i in range(len(self.global_plugin_names)):
            modname = self.global_plugin_names[i]
            filename = Path(self.global_pluginpath) / f"{modname}.py"
            if filename.exists():
                modname = f"plugins.{modname}"
                loader = importlib.machinery.SourceFileLoader(modname, str(filename))
                try:
                    module = loader.load_module(modname)
                    self.global_plugins[i] = module
                except Exception as e:
                    logger.error(f"Failed to Load global plugin {modname}")

        # plugins must be called ...plugin.py, so other modules in the same
        # directory are not falsely loaded (allows for plugin decomposition)
        for plugin_path in plugin_paths:
            for path in plugin_path.glob("*_plugin.py"):
                if path.exists():
                    modname = f"plugins.{path.stem}"
                    logger.info(f"importing {modname}")
                    loader = importlib.machinery.SourceFileLoader(modname, str(path))
                    try:
                        module = loader.load_module(modname)
                        pluginname = path.stem.replace("_plugin", "")
                        self.available_plugins[pluginname] = module.HELP_DESC
                    except Exception as e:
                        logger.warning(e)
        await self.enter_plugins_to_db()

    async def enter_plugins_to_db(self):
        # we now check, if all loaded plugins have an entry in the database
        # if not, we add it
        # TODO: - do we want to remove database entries when a plugin disappears?
        #         problem: development of plugin with errors -> deletion?!?! not wanted!
        #       - How do we guarantee the uniqueness of filenames among directories?
        cursor = self.conn.cursor()
        res = cursor.execute(
            """
            SELECT *
            FROM plugins;
            """
        )
        dbplugins = res.fetchall()
        for ap in list(self.available_plugins.keys()) + self.global_plugin_names:
            if (ap,) not in dbplugins:
                # add plugin to db
                self.conn.execute(
                    """
                    INSERT INTO plugins (pluginname) VALUES (?);
                    """,
                    (ap,),
                )
                self.conn.commit()

    async def listen(self):
        async def handle_invite_event(room, event):
            try:
                jrooms = await self.client.joined_rooms()
                jrooms = jrooms.rooms
            except:
                logger.warning(f"Not joining room {room.room_id}")
                return
            if self.allowed_rooms and room.room_id not in self.allowed_rooms:
                logger.info(
                    f"Room {room.room_id} not in whitelist. Ignore invite event"
                )
                return
            if room.room_id not in jrooms:
                logger.info(f"Try joining room {room.room_id}")
                await asyncio.sleep(0.5)
                response = await self.client.join(room.room_id)
                await asyncio.sleep(0.5)
                if type(response) == nio.responses.JoinResponse:
                    self.active_rooms.add(await MatrixRoom.new(self, room))
                else:
                    logger.warning(f"Couldn't joing the room: {response}")
            else:
                logger.warning(f"Not joining room {room.room_id}")
                logger.warning(f"Already joined.")

        async def handle_text_event(room, event):
            # we ignore messages older than 5secs before last sync to solve
            # joining new room and interpreting old messages problem
            logger.debug(str(event))
            if (self.last_sync_time - 5) * 1000 > event.server_timestamp:
                logger.debug(f"Ignoring old event in room {room.room_id}")
                return

            if event.sender == self.client.user:
                logger.debug(f"Ignoring own message in room {room.room_id}")
                return

            matching_rooms = [
                mroom for mroom in self.active_rooms if mroom.room_id == room.room_id
            ]
            if matching_rooms:
                try:
                    await matching_rooms[0].handle_text_event(event)
                except Exception as e:
                    traceback.print_exc()
                    logger.warning(e)
                    try:
                        k = traceback.format_exc()
                        if "ADMIN" in self.environment:
                            admin = self.environment["ADMIN"]
                            k += f"\nPlease contact {admin} for bug fixing"
                        else:
                            k += "\nPlease contact the plugin creator"
                        self.nio_room = room
                        await Plugin.send_text(self, k)
                    except Exception as e:
                        traceback.print_exc()
                        logger.warning(e)
            else:
                logger.info(f"Ignoring text event in non-active room {room.room_id}")

        async def event_cb(room, *args):
            event = args[0]
            logger.debug(80 * "=")
            # pprint(vars(event))
            if room.room_id in self.client.rooms:
                logger.debug(
                    f"{type(event)} in room {self.client.rooms[room.room_id].display_name})"
                )
            else:
                logger.debug(type(event), "in room", room.room_id)

            if type(event) == nio.events.invite_events.InviteMemberEvent:
                await handle_invite_event(room, event)
            elif type(event) == nio.events.room_events.RoomMessageText:
                await handle_text_event(room, event)
            elif type(event) == nio.events.room_events.RoomMemberEvent:
                name = event.source.get("sender")
                logger.info(
                    f"membership of {name} changed in room {room.room_id} from {event.prev_membership} to {event.membership}"
                )
            elif type(event) == nio.MegolmEvent:
                logger.debug(f"account shared: {self.client.olm_account_shared}")
                logger.warning("Unable to decrypt event")
                print(f"Event session ID {event.session_id}")
                r = nio.crypto.OutgoingKeyRequest(event.session_id, None, None, None)
                self.client.store.remove_outgoing_key_request(r)
                if event.session_id in self.client.olm.outgoing_key_requests.keys():
                    del self.client.olm.outgoing_key_requests[event.session_id]
                res = await self.client.request_room_key(
                    event
                )  # should do updating by itself
                # event_cb(room, event)
            else:
                logger.debug("Ignoring unknown type event")

        async def response_cb(response):
            logger.debug("Got response")
            logger.debug(type(response))
            self.last_sync_time = time.time()
            logger.debug("Ignoring response")

        async def todevice_cb(request):
            logger.debug(80 * "=")
            logger.debug("Got to device request")
            logger.debug(type(request))
            logger.debug("Ignoring to device request")

        async def ephemeral_cb(arg1, arg2):
            logger.debug(80 * "=")
            logger.debug("Got ephemeral dings")
            logger.debug(f"{type(arg1)}, {type(arg2)}")
            logger.debug("Ignoring ephemeral dings")

        async def kick_response_cb(response):
            logger.info("Getting kicked")

        logger.info(f"{self.botname} lauert nun.")

        self.client.add_event_callback(event_cb, nio.Event)
        self.client.add_event_callback(event_cb, nio.InviteMemberEvent)

        self.client.add_to_device_callback(
            todevice_cb, nio.events.to_device.ToDeviceEvent
        )
        self.client.add_ephemeral_callback(
            ephemeral_cb, nio.events.ephemeral.EphemeralEvent
        )
        self.client.add_response_callback(response_cb, nio.Response)
        self.client.add_response_callback(
            kick_response_cb, nio.RoomKickResponse
        )  # DOESNT WORK

        if False:
            for room_id in self.active_rooms:
                await self.introduce_bot(room_id)

        await self.client.sync_forever(30000)

    async def start(self):
        await self.read_plugins()
        await self.start_global_plugins()
        await self.load_rooms()
        await self.listen()

    async def get_private_room_with_user(self, user_id):
        """
        Finds an existing room with the given user.
        If no room exists a new room is created with only the user and the bot
        @return: the room id of the private room
        """

        # Find an exiting room with only user_id and bot.user_id
        rooms = (await self.client.joined_rooms()).rooms
        for room in rooms:
            members = [
                m.user_id for m in (await self.client.joined_members(room)).members
            ]
            if len(members) != 2:
                continue
            if sorted(members) == sorted([user_id, self.client.user_id]):
                return room

        logger.info(f"No Common room with {user_id} found. Creating a new Matrix Room")

        # Create a new room
        create_response = await self.client.room_create(
            is_direct=True,
            preset=nio.RoomPreset.private_chat,
            invite=[user_id],
            initial_state=[
                nio.event_builders.state_events.EnableEncryptionBuilder().as_dict(),
                nio.event_builders.state_events.ChangeHistoryVisibilityBuilder(
                    "shared"
                ).as_dict(),
            ],
            power_level_override={"users_default": 100},
            # power_level_override={"users":{user_id:100}}, # This does not work as expected, maybe cause user_id hat not joined
        )
        room_id = create_response.room_id
        logger.info(f"Created new Room with id {room_id}. Waiting for next sync")
        # Wait for the next sync, until the new room is in our storage and we can send the message in the new room
        await self.client.synced.wait()
        logger.info("Synced")

        # Add the new room to bernd managed rooms
        mr = await MatrixRoom.new(self, self.client.rooms[room_id])
        self.active_rooms.add(mr)

        return room_id
