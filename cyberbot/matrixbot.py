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
from http_server import BotHTTPServer

import nio



class MatrixBot:


    def __init__(self,
            username,
            password,
            homeserver,
            botname="Matrix Bot",
            deviceid="MATRIXBOT",
            dbpath="./matrixbot.sqlite",
            pluginpath=[ "./plugins" ],
            store_path=None,
            bind_address="localhost",
            bind_port=8080,
            environment={}):

        if not store_path:
            store_path = Path(os.getcwd()) / "store"
        else:
            store_path = Path(store_path)

        if not store_path.is_dir():
            logging.info(f"Creating store directory in {store_path}")
            try:
                os.mkdir(store_path)
            except Exception as e:
                logging.error("Failed to create store path. Check permissions.")
                print(e)
                sys.exit(-1)

        # this is a small hack to add the plugins to the import search path
        for path in pluginpath:
            sys.path.append(path)

        # create http server
        self.http_server = BotHTTPServer(bind_address, bind_port)

        logging.info(f"Store path: {store_path}")

        self.client = nio.AsyncClient(homeserver, username, device_id=deviceid, store_path=str(store_path))

        self.password = password
        self.botname = botname

        self.dbpath = dbpath
        self.load_db(dbpath)
        self.pluginpath = pluginpath
        self.environment = environment
        self.last_sync_time = 0

        self.active_rooms = set()
        self.available_plugins = {}


    async def start_http_server(self):
        await self.http_server.start()


    async def login(self):
        import socket
        hname = socket.gethostname()
        response = await self.client.login(self.password, device_name=hname)
        if type(response) == nio.LoginError:
            logging.error("""There was an error while logging in. Please check
credentials""")
            sys.exit(-1)
        k = await self.client.sync() # otherwise all past messages will be handled
        self.last_sync_time = time.time()
        if self.client.should_upload_keys:
            await self.client.keys_upload()
        cur_displayname = (await self.client.get_displayname()).displayname
        logging.info(f"Current displayname: {cur_displayname}")
        if cur_displayname != self.botname:
            logging.info(f"Changing displayname to {self.botname}")
            await self.client.set_displayname(self.botname)

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
        # attention here, meaning of "plugin_data" has changed
        # room_data: global room data
        # plugin_data: global plugin data
        # room_plugin_data: data local to a plugin x room combination
        # room_plugins: which plugins are loaded in which room
        if not all((t,) in tables for t in ["rooms", "plugins", "room_plugins", "room_data", "plugin_data", "room_plugin_data"]):
            c.execute("""
            CREATE TABLE rooms (
                roomid     VARCHAR PRIMARY KEY
            );
            """)
            c.execute("""
            CREATE TABLE plugins (
                pluginname VARCHAR PRIMARY KEY
            );
            """)
            c.execute("""
            CREATE TABLE room_plugins (
                roomid     VARCHAR,
                pluginname VARCHAR,
                PRIMARY KEY (roomid, pluginname)
            );
            """)
            c.execute("""
            CREATE TABLE room_data (
                roomid     VARCHAR,
                key        VARCHAR,
                value      TEXT,
                PRIMARY KEY (roomid, key)
            );
            """)
            c.execute("""
            CREATE TABLE plugin_data (
                pluginname VARCHAR,
                key        VARCHAR,
                value      TEXT,
                PRIMARY KEY (pluginname, key)
            );
            """)
            c.execute("""
            CREATE TABLE room_plugin_data (
                roomid     VARCHAR,
                pluginname VARCHAR,
                key        VARCHAR,
                value      TEXT,
                PRIMARY KEY (roomid, pluginname, key)
            );
            """)


    async def load_rooms(self):
        joined_rooms = self.client.rooms
        print(joined_rooms)
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
        plugin_paths = [Path(path) for path in self.pluginpath]
        logging.info("Reading available plugins from: {}".format(plugin_paths))

        help_module = None

        # plugins must be called ...plugin.py, so other modules in the same
        # directory are not falsely loaded (allows for plugin decomposition)
        for plugin_path in plugin_paths:
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

    async def enter_plugins_to_db(self):
        # we now check, if all loaded plugins have an entry in the database
        # if not, we add it
        # TODO: - do we want to remove database entries when a plugin disappears?
        #         problem: development of plugin with errors -> deletion?!?! not wanted!
        #       - How do we guarantee the uniqueness of filenames among directories?
        cursor = self.conn.cursor()
        res = cursor.execute("""
        SELECT *
        FROM plugins;
        """)
        dbplugins = res.fetchall()
        for ap in self.available_plugins.keys():
            if (ap,) not in dbplugins:
                # add plugin to db
                self.conn.execute("""
                INSERT INTO plugins (pluginname) VALUES (?);
                """, (ap,))
                self.conn.commit()

    async def listen(self):

        async def handle_invite_event(room, event):
            try:
                jrooms = await self.client.joined_rooms()
                print(jrooms)
                jrooms = jrooms.rooms
                print(jrooms)
            except:
                logging.warning(f"Not joining room {room.room_id}")
                return
            if room.room_id not in jrooms:
                logging.info(f"Try joining room {room.room_id}")
                await asyncio.sleep(0.5)
                response = await self.client.join(room.room_id)
                await asyncio.sleep(0.5)
                if type(response) == nio.responses.JoinResponse:
                    self.active_rooms.add(await MatrixRoom.new(self,room))
                    pprint(vars(response))
                else:
                    print(type(response))
                    print(vars(response))
                    print(response.message)
                    logging.warning(f"Couldn't joing the room: {response}")
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
                try:
                    await matching_rooms[0].handle_text_event(event)
                except Exception as e:
                    traceback.print_exc()
                    logging.warning(e)
                    try:
                        k = traceback.format_exc()
                        if "ADMIN" in self.environment:
                            admin = self.environment['ADMIN']
                            k += f"\nPlease contact {admin} for bug fixing"
                        else:
                            k += "\nPlease contact the plugin creator"
                        self.nio_room = room
                        await Plugin.send_text(self, k)
                    except Exception as e:
                        traceback.print_exc()
                        logging.warning(e)
            else:
                logging.info("Ignoring text event in non-active room")

        async def event_cb(room, *args):
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
                print(f"Event session ID {event.session_id}")
                r = nio.crypto.OutgoingKeyRequest(event.session_id, None, None, None)
                self.client.store.remove_outgoing_key_request(r)
                if (event.session_id in self.client.olm.outgoing_key_requests.keys()):
                    del self.client.olm.outgoing_key_requests[event.session_id]
                res = await self.client.request_room_key(event) # should do updating by itself
                print(res)
                #event_cb(room, event)
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

