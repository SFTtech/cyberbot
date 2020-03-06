import asyncio
import sys
import importlib
import os

from pathlib import Path
from pprint import pprint

from matrixroom import MatrixRoom

import nio



class MatrixBot:
    """
    TODO:
        - refresh access token if expired
    """

    def __init__(self, username, password, server,
            botname="Matrix Bot", deviceid="MATRIXBOT", adminusers=[]):

        store_path = Path(__file__).parent.parent / "store"
        if not store_path.is_dir():
            print(f"Creating store directory in {store_path}")
            os.mkdir(store_path)

        self.client = nio.AsyncClient(server, username, device_id=deviceid,
                store_path=store_path)

        self.password = password
        self.active_rooms = set()
        self.handlers = []
        self.botname = botname
        self.adminusers = adminusers
        print("Admins: {}".format(" ".join(adminusers)))


    async def login(self):
        response = await self.client.login(self.password)
        if type(response) == nio.LoginError:
            sys.stderr.write("""There was an error while logging in. Please check
                    credentials""")
            sys.exit(-1)
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
            sys.stderr.write(f"""There was an error fetching joined
                    rooms: {response.message}""")
            sys.exit(-1)
        return response.rooms
    

    async def join_rooms(self, rooms):
        assert(self.client.logged_in)
        self.ok_rooms = rooms # we will accept invites from these rooms
        joined_rooms = await self.get_joined_rooms()
        print("Already joined following rooms:\n\t", end="")
        print("\n\t".join(joined_rooms))
        print()
        print(80*"-")

        tojoin_rooms = [room for room in rooms if room not in joined_rooms]
        #unused_rooms = [room for room in joined_rooms if room not in rooms]
        unused_rooms = []

        r = await asyncio.gather(*(self.client.join(room) for room in tojoin_rooms))
        k = list(zip(tojoin_rooms, r))
        if any(type(response) == nio.JoinError for _,response in k):
            sys.stderr.write("There was an Error joining these rooms:\n\t")
            sys.stderr.write("\n\t".join(f"{room}: {response.message}"
                for room,response in k if type(response) == nio.JoinError))
            sys.stderr.write("\n\n")

        self.active_rooms.update(set(room for room,response in k if type(response != nio.JoinError)))

        if unused_rooms:
            print("Leaving already old rooms...")
            await asyncio.gather(*(self.client.room_leave(room) for room in unused_rooms))

        joined_rooms = await self.get_joined_rooms()
        print("Active rooms:\n\t", end="")
        print("\n\t".join(joined_rooms))
        print()
        print(80*"-")

        if (await self.client.get_displayname()) != self.botname:
            print(f"Setting Displayname to {self.botname}...")
            await self.client.set_displayname(self.botname)


    async def load_plugins(self, plugindir="plugins"):
        plugin_path = Path(__file__).resolve().parent.parent / plugindir
        print("Loading plugins from: {}".format(plugin_path))
        help_desc = []

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


                    # Provide every module with a set of relevant environment vars
                    module.DB_PATH = 'matrix.db'     # relative path to the sqlite3-dtb
                    module.COUNTER_TAB = 'counters' # Name of counter table in database
                    module.RATELIMIT_TAB = 'ratelimit' # Name of ratelimit table in database
                    module.CORRECTION_TAB = 'corrections' # Name of correction table in database
                    module.TRUSTED_ROOMS = self.ok_rooms    # Trusted rooms to join
                    module.CONFIG_USER = self.client.user   # Username, read from config file
                    module.CONFIG_SERVER = self.client.homeserver   # Server, read from config file

                    # skip help module, collect all help texts before registering
                    if (modname == 'plugins.help_plugin'):
                        help_module = module
                        help_modname = modname
                    else:
                        module.register_to(self)
                        print(f"  [+] {modname} loaded")
                except ImportError as e:
                    print(f"  [!] {modname} not loaded: {str(e)}")
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
        print(f"  [+] {help_modname} loaded")

        # Start polling and save a handle to the child thread
        #child_thread = bot.start_polling()




    def add_handler(self, handler):
        """
        should be called by plugins when registering bot
        """
        self.handlers.append(handler)



    async def listen(self, mode):
        has_old_api = False
        try:
            import matrix_bot_api.mhandler
            has_old_api = True
        except:
            pass




        async def response_cb(response):
            pass
            #print(type(response))

        async def event_cb(room, *args):
            """
            TODO: add try catch and send exception text into room
            """
            event = args[0]
            print(80 * "=")
            if room.room_id in self.client.rooms:
                print(type(event), "in room", self.client.rooms[room.room_id].display_name)
            else:
                print(type(event), "in room", room.room_id)

            if type(event) == nio.events.invite_events.InviteMemberEvent:
                return
                if room.room_id in self.ok_rooms or \
                        event.sender in self.adminusers:
                            # TODO: check return
                            await asyncio.sleep(0.5)
                            response = await self.client.join(room.room_id)
                            print(response)
                print()
                return


            m_room = MatrixRoom(self.client, room)

            if type(event) == nio.events.room_events.RoomMessageText:
                print("\t" + str(event))

            if type(event) == nio.events.room_events.RoomMemberEvent:
                name = event.source.get("sender")
                print(f"{name} joined room")

            if type(event) == nio.MegolmEvent:
                print("account shared:", self.client.olm_account_shared)
                print("Unable to decrypt event")

                k = await self.client.share_group_session(event.room_id,
                       ignore_unverified_devices=False)
                print(k)

                try:
                    print("Get missing sessions")
                    #breakpoint()
                    k = self.client.get_missing_sessions(room.room_id)
                    print(k)
                except Exception as e:
                    print(e)

                try:
                    print("uploading keys")
                    k = await self.client.keys_upload()
                    print(k)
                except Exception as e:
                    print(e)
                try:
                    print("querying keys")
                    k = await self.client.keys_query()
                    print(k)
                except Exception as e:
                    print(e)
                try:
                    print("Trying to decrypt event")
                    k = await self.client.decrypt_event(event)
                    print(k)
                except Exception as e:
                    print(e)
                # print(event)
                #await self.client.share_group_session(event.room_id,
                #        ignore_unverified_devices=True)
                #print("Missing sessions:", self.client.get_missing_sessions(event.room_id))
                #print("device store:", self.client.device_store._entries.keys())
                #k = self.client.get_missing_sessions(event.room_id)
                #print("Missing sessions:", k)
                #k = await self.client.keys_claim(self.client.device_store._entries)
                #k = await self.client.keys_claim(k)
                #print("keys claim", k)
                #k = await self.client.keys_upload()
                #print(k)
                #print("Keys query:", await self.client.keys_query())
                # try:
                    # k = await self.client.request_room_key(event)
                    # print("await client request room key:", k)
                    # pass
                # except Exception as e:
                    # print(e)
                # try:
                    # k = await self.client.continue_key_share(event)
                    # print("continue key share:", k)
                # except Exception as e:
                    # print(e)
                # try:
                    # k = await self.client.keys_query()
                    # print("keys_query:", k)
                # except Exception as e:
                    # print(e)
                # try:
                    # k = await self.client.keys_upload()
                    # print("keys_upload:", k)
                # except Exception as e:
                    # print(e)
              # #  try:
              #      k = await self.client.decrypt_event(event)
              #      print("client decrypt event", k)
              #  except nio.exceptions.EncryptionError as e:
              #      #k = await self.client.request_room_key(event)
              #      #print("await client request roo key:", k)
              #      #k = await self.client.decrypt_event(event)
              #      #print("cleint decrypt event", k)
              #      print("Error Decrypting\n\n", e)
            #print(type(event))
            #print(self.client.should_query_keys,self.client.should_upload_keys,
            #        self.client.should_claim_keys)

            #print(self.client.olm_account_shared)
            #print(self.client.get_users_for_key_claiming())
            for handler in self.handlers:
                pass
                #print(type(event))
                #if type(event) == nio.RoomMessageText:
                    #if handler.test_callback(room, event.source):
                        #await handler.handle_callback(m_room, event.source)

        def todevice_cb(request):
            print(80 * "=")
            print("Got to device request")
            print(type(request))

        def ephemeral_cb(arg1, arg2):
            print(80 * "=")
            print("Got ephemeral dings")
            print(type(arg1), type(arg2))

        print(f"{self.botname} lauert nun.")


        # await self.client.sync()
        # # k = await self.client.share_group_session(room_id="!wNYKPZiPMyfSiFYPzJ:stusta.de",
                # # ignore_unverified_devices=False)
        # k = await self.client.share_group_session(room_id="!wNYKPZiPMyfSiFYPzJ:stusta.de",
                # ignore_unverified_devices=True)
        # print(k)
        # print(vars(self.client))
        # response = await self.client.room_send(
                # #room_id="!GEEFteJNCNZoEmBfhD:matrix.org",
                # room_id="!wNYKPZiPMyfSiFYPzJ:stusta.de",
                # message_type="m.room.message",
                # content={
                    # "msgtype": "m.text",
                    # "body": "encrypted test",
                # },
                # ignore_unverified_devices=True)
        # print(response)
        # await self.client.sync_forever(30000)
        # self.client.add_response_callback(response_cb, nio.Response)
        # self.client.add_event_callback(event_cb, nio.Event)


        self.client.add_event_callback(event_cb, nio.Event)
        self.client.add_to_device_callback(todevice_cb, nio.events.to_device.ToDeviceEvent)
        self.client.add_ephemeral_callback(ephemeral_cb, nio.events.ephemeral.EphemeralEvent)

        await self.client.sync_forever(30000)
