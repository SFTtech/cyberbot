import asyncio
import sys
import os
import time
import importlib
import logging
import traceback
import sqlite3

from pathlib import Path
from pprint import pprint

from matrixroom import MatrixRoom
from plugin import Plugin

import nio



class MatrixBot:


    def __init__(self,
            username,
            password,
            server,
            botname="Matrix Bot",
            deviceid="MATRIXBOT",
            dbpath="./matrixbot.sqlite",
            plugindir="plugins",
            store_path=None,
            environment={}):

        if not store_path:
            store_path = Path(os.getcwd()) / "store"

        if not store_path.is_dir():
            logging.info(f"Creating store directory in {store_path}")
            try:
                os.mkdir(store_path)
            except Exception as e:
                logging.error("Failed to create store path. Check permissions.")
                print(e)
                sys.exit(-1)


        logging.info(f"Store path: {store_path}")

        self.client = nio.AsyncClient(server, username, device_id=deviceid, store_path=str(store_path))

        self.password = password
        self.botname = botname

        self.dbpath = dbpath
        self.load_db(dbpath)
        self.plugindir = plugindir
        self.environment = environment
        self.last_sync_time = 0

        self.active_rooms = set()


    async def login(self):
        response = await self.client.login(self.password)
        if type(response) == nio.LoginError:
            logging.error("""There was an error while logging in. Please check
credentials""")
            sys.exit(-1)
        k = await self.client.sync() # otherwise all past messages will be handled
        self.last_sync_time = time.time()
        if self.client.should_upload_keys:
            await self.client.keys_upload()


    async def __aenter__(self):
        await self.login()
        return self


    async def __aexit__(self, exc_type, exc_value, exc_tb):
        await self.client.close()


    def load_db(self, dbname):
        self.conn = sqlite3.connect(dbname)
        c = self.conn.cursor()
        tables = c.execute("""
            SELECT name
            FROM sqlite_master 
            WHERE type ='table' AND name NOT LIKE 'sqlite_%';
            """).fetchall()
        if not all((t,) in tables for t in ["rooms", "room_plugins", "plugin_data"]):
            c.execute("""
            CREATE TABLE rooms (
                roomid     VARCHAR PRIMARY KEY
            );
            """)
            c.execute("""
            CREATE TABLE room_plugins (
                pluginid   INTEGER PRIMARY KEY AUTOINCREMENT,
                roomid     VARCHART,
                pluginname VARCHAR
            );
            """)
            c.execute("""
            CREATE TABLE plugin_data (
                pluginid   INTEGER,
                key        VARCHAR,
                value      TEXT,
                PRIMARY KEY (pluginid, key)
            );
            """)


    async def load_rooms(self):
        joined_rooms = self.client.rooms
        cursor = self.conn.cursor()
        res = cursor.execute("""
        SELECT *
        FROM rooms;
        """)
        dbrooms = res.fetchall()
        for rid,nio_room in joined_rooms.items():
            if (rid,) in dbrooms:
                mr = MatrixRoom(
                        matrixbot=self,
                        nio_room=nio_room,
                    )
                await mr.load_plugins()
                self.active_rooms.add(mr)


    

    async def read_plugins(self):
        plugin_path = Path(self.plugindir)
        logging.info("Reading available plugins from: {}".format(plugin_path))
        #help_desc = ["!reload \t\t-\t reload plugins"]

        help_module = None

        self.available_plugins = {}

        # plugins must be called ...plugin.py, so other modules in the same
        # directory are not falsely loaded (allows for plugin decomposition)
        for filename in plugin_path.glob("*_plugin.py"):
            if filename.exists():
                modname = f'plugins.{filename.stem}'
                loader = importlib.machinery.SourceFileLoader(modname, str(filename))
                try:
                    module = loader.load_module(modname)
                    pluginname = filename.stem.replace("_plugin","")
                    self.available_plugins[pluginname] = module.HELP_DESC
                except Exception as e:
                    logging.warning(e)


    async def listen(self):

        async def handle_invite_event(room, event):
            try:
                jrooms = await self.client.joined_rooms()
                jrooms = jrooms.rooms
            except:
                logging.warning(f"Not joining room {room.room_id}")
                return
            if room.room_id not in jrooms:
                logging.info(f"Try joining room {room.room_id}")
                # TODO: check return
                await asyncio.sleep(0.5)
                response = await self.client.join(room.room_id)
                await asyncio.sleep(0.5)
                if type(response) == nio.JoinResponse:
                    #pprint(vars(response))
                    self.active_rooms.add(await MatrixRoom.new(self,room))
            else:
                logging.warning(f"Not joining room {room.room_id}")
                logging.warning(f"Already joined.")


        async def handle_text_event(room, event):
            # we ignore messages older than 5secs before last sync to solve
            # joining new room and interpreting old messages problem
            logging.debug(str(event))
            if (self.last_sync_time-5)*1000 > event.server_timestamp:
                logging.debug("Ignoring old event")
                return

            if event.sender == self.client.user:
                logging.debug("Ignoring own message")
                return

            matching_rooms = [mroom for mroom in self.active_rooms if
                    mroom.room_id == room.room_id]
            if matching_rooms:
                await matching_rooms[0].handle_text_event(event)
            else:
                logging.info("Ignoring text event in non-active room")

        async def event_cb(room, *args):
            """
            TODO: add try catch and send exception text into room
            """
            event = args[0]
            logging.debug(80 * "=")
            #pprint(vars(event))
            if room.room_id in self.client.rooms:
                logging.debug(f"{type(event)} in room {self.client.rooms[room.room_id].display_name})")
            else:
                logging.debug(type(event), "in room", room.room_id)

            if type(event) == nio.events.invite_events.InviteMemberEvent:
                await handle_invite_event(room, event)
            elif type(event) == nio.events.room_events.RoomMessageText:
                await handle_text_event(room, event)
            elif type(event) == nio.events.room_events.RoomMemberEvent:
                name = event.source.get("sender")
                logging.info(f"{name} joined room")
            elif type(event) == nio.MegolmEvent:
                logging.debug("account shared:", self.client.olm_account_shared)
                logging.warning("Unable to decrypt event")
            else:
                logging.debug("Ignoring unknown type event")


        async def response_cb(response):
            logging.debug("Got response")
            logging.debug(type(response))
            self.last_sync_time = time.time()
            logging.debug("Ignoring response")

        async def todevice_cb(request):
            logging.debug(80 * "=")
            logging.debug("Got to device request")
            logging.debug(type(request))
            logging.debug("Ignoring to device request")

        async def ephemeral_cb(arg1, arg2):
            logging.debug(80 * "=")
            logging.debug("Got ephemeral dings")
            logging.debug(f"{type(arg1)}, {type(arg2)}")
            logging.debug("Ignoring ephemeral dings")

        async def kick_response_cb(response):
            logging.info("Getting kicked")


        logging.info(f"{self.botname} lauert nun.")




        self.client.add_event_callback(event_cb, nio.Event)
        self.client.add_event_callback(event_cb, nio.InviteMemberEvent)

        self.client.add_to_device_callback(todevice_cb, nio.events.to_device.ToDeviceEvent)
        self.client.add_ephemeral_callback(ephemeral_cb, nio.events.ephemeral.EphemeralEvent)
        self.client.add_response_callback(response_cb, nio.Response)
        self.client.add_response_callback(kick_response_cb, nio.RoomKickResponse) # DOESNT WORK


        if False:
            for room_id in self.active_rooms:
                await self.introduce_bot(room_id)

        await self.client.sync_forever(30000)

