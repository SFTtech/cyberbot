import asyncio
import sys
import importlib
import os
import time
import logging
import traceback

from pathlib import Path
from pprint import pprint

from matrixroom import MatrixRoom

import nio



class MatrixBot:
    """
    TODO: add whitelist/blacklist plugins
    """

    def __init__(self,
            username,
            password,
            server,
            botname="Matrix Bot",
            deviceid="MATRIXBOT",
            adminusers=[],
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
        self.active_rooms = set()
        self.handlers = []
        self.botname = botname
        self.adminusers = adminusers
        self.last_sync_time = 0
        self.environment=environment

        logging.info("Admins: {}".format(" ".join(adminusers)))


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


    async def get_joined_rooms(self):
        response = await self.client.joined_rooms()
        if type(response) == nio.JoinedRoomsError:
            logging.error(f"""There was an error fetching joined
rooms: {response.message}""")
            sys.exit(-1)
        return response.rooms
    

    async def join_rooms(self, rooms):
        self.ok_rooms = rooms # we will accept invites from these rooms
        joined_rooms = await self.get_joined_rooms()
        self.active_rooms.update(set(joined_rooms))
        joined_names = [self.client.rooms[rid].display_name
                if rid in self.client.rooms
                else rid
                for rid in joined_rooms]
        logging.debug("Already joined following rooms:\n\t\t{}"\
                .format("\n\t\t".join(joined_names)))


        tojoin_rooms = [room for room in rooms if room not in joined_rooms]
        #unused_rooms = [room for room in joined_rooms if room not in rooms]
        unused_rooms = []

        r = await asyncio.gather(*(self.client.join(room) for room in tojoin_rooms))
        k = list(zip(tojoin_rooms, r))
        if any(type(response) == nio.JoinError for _,response in k):
            logging.warning("There was an Error joining these rooms:\n\t\t{}"\
                    .format("\n\t\t".join(f"{room}: {response.message}"
                for room,response in k if type(response) == nio.JoinError)))

        self.active_rooms.update(set(room for room,response in k if type(response != nio.JoinError)))

        if unused_rooms:
            logging.info("Leaving already old rooms...")
            await asyncio.gather(*(self.client.room_leave(room) for room in unused_rooms))

        joined_rooms = await self.get_joined_rooms()
        joined_names = [self.client.rooms[rid].display_name
                if rid in self.client.rooms
                else rid
                for rid in joined_rooms]
        logging.info("Active rooms:\n\t\t{}"\
                .format("\n\t\t".join(joined_names)))

        if (await self.client.get_displayname()) != self.botname:
            logging.info(f"Setting Displayname to {self.botname}...")
            await self.client.set_displayname(self.botname)


    async def load_plugins(self, plugindir="plugins"):
        self.handlers = []
        plugin_path = Path(__file__).resolve().parent.parent / plugindir
        logging.info("Loading plugins from: {}".format(plugin_path))
        help_desc = ["!reload \t\t-\t reload plugins"]

        help_module = None

        # plugins must be called ...plugin.py, so other modules in the same
        # directory are not falsely loaded (allows for plugin decomposition)
        for filename in plugin_path.glob("*_plugin.py"):
            if (plugin_path / filename).exists():
                modname = f'plugins.{filename.stem}'
                loader = importlib.machinery.SourceFileLoader(modname, str(filename))
                try:
                    module = loader.load_module(modname)

                    # collect plugin help texts
                    help_text_arr = module.HELP_DESC.split('\n') # allow multiple desc
                    for h in help_text_arr:
                        help_desc.append(h)


                    module.TRUSTED_ROOMS = self.ok_rooms.copy()    # Trusted rooms to join
                    module.ENVIRONMENT = self.environment.copy()

                    # skip help module, collect all help texts before registering
                    if (modname == 'plugins.help_plugin'):
                        help_module = module
                        help_modname = modname
                    else:
                        module.register_to(self)
                        logging.info(f"  [+] {modname} loaded")
                except ImportError as e:
                    logging.info(f"  [!] {modname} not loaded: {str(e)}")
        # Build the help message from the collected plugin description fragments
        help_txt = '\n'.join([
                f"{self.botname} Commands and Capabilities",
                '-' * 80,
                '',
                ] + [ e for e in sorted(help_desc) if e != '' ])

        with open('help_text', 'w') as f:
            f.write(help_txt)

        # load the help module after all help texts have been collected
        help_module.register_to(self)
        logging.info(f"  [+] {help_modname} loaded")

        # Start polling and save a handle to the child thread
        #child_thread = bot.start_polling()




    def add_handler(self, handler):
        """
        should be called by plugins when registering bot
        """
        self.handlers.append(handler)


    async def introduce_bot(self,roomid):
        try:
            logging.info(f"Introducing myself to {roomid}")
            m_room = MatrixRoom(self.client, self.client.rooms[roomid])
            await m_room.send_text(f"""Hi, my name is {self.botname}! I was just (re)started. Type !help to see my (new) capabilities.""")
        except Exception as e:
            logging.info(e)


    async def listen(self):
        might_use_old_api = False # currently unused
        try:
            import matrix_bot_api.mhandler
            might_use_old_api = True
        except ModuleNotFoundError:
            might_use_old_api = False
            pass


        async def handle_invite_event(room, event):
            if (room.room_id in self.ok_rooms or \
                    event.sender in self.adminusers) and \
                    room.room_id not in await self.get_joined_rooms():
                logging.info(f"Try joining room {room.room_id}")
                # TODO: check return
                await asyncio.sleep(0.5)
                response = await self.client.join(room.room_id)
                if type(response) == nio.JoinResponse:
                    await self.introduce_bot(room.room_id)
            else:
                logging.warning(f"Not joining room {room.room_id}")
                logging.warning(f"Room not trusted or user not admin")

        async def handle_text_event(room, event):
            # we ignore messages older than 5secs before last sync to solve
            # joining new room and interpreting old messages problem
            logging.debug(str(event))
            if (self.last_sync_time-5)*1000 > event.server_timestamp:
                logging.debug("Ignoring old event")
                return

            if event.source['content']['body'].startswith("!reload"):
                logging.info("Reloading plugins...")
                await self.load_plugins()
                return

            m_room = MatrixRoom(self.client, room)
            if event.sender == self.client.user:
                logging.debug("Ignoring own message")
                return

            for handler in self.handlers:
                try:
                    if handler.test_callback(room, event.source):
                        logging.info("A handler was triggered")
                        await handler.handle_callback(m_room, event.source)
                except Exception as e:
                    await m_room.send_html(f"<pre><code>{traceback.format_exc()}</code></pre>")
                    logging.warning(traceback.format_exc())

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


        logging.info(f"{self.botname} lauert nun.")




        self.client.add_event_callback(event_cb, nio.Event)
        self.client.add_event_callback(event_cb, nio.InviteMemberEvent)

        self.client.add_to_device_callback(todevice_cb, nio.events.to_device.ToDeviceEvent)
        self.client.add_ephemeral_callback(ephemeral_cb, nio.events.ephemeral.EphemeralEvent)
        self.client.add_response_callback(response_cb, nio.Response)


        if False:
            for room_id in self.active_rooms:
                await self.introduce_bot(room_id)

        await self.client.sync_forever(30000)
