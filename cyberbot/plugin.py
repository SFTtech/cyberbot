import nio
import asyncio
import logging
import importlib
import pathlib
import shlex
import traceback
import re

from itertools import compress
from pathlib import Path

class Plugin:
    def __init__(self, mroom, pluginname):
        self.mroom = mroom

        self.pluginname = pluginname

        self.handlers = []
        self.module = None
        self.nio_room = mroom.nio_room
        self.bot = mroom.bot
        self.client = mroom.bot.client

        self.tasks = set()
        self.log = logging.getLogger(f"{__name__}.{mroom.room_id}.{pluginname}")

    async def load(self):
        filename = self.pluginname + "_plugin.py"
        full_plugin_path = None
        self.log.info(f"Loading ...")
        for path in self.bot.pluginpath:
            p = Path(path).resolve()
            if (p / filename).exists():
                full_plugin_path = p / filename
                break
        if full_plugin_path is None:
            self.log.warning(
                f"Couldn't load plugin {self.pluginname}: file does not exist"
            )
            return False

        modname = f"plugins.{self.pluginname}"
        loader = importlib.machinery.SourceFileLoader(modname, str(full_plugin_path))
        try:
            self.module = loader.load_module(modname)
            self.module.ENVIRONMENT = self.bot.environment.copy()
            await self.module.register_to(self)
            return True
        except Exception as e:
            traceback.print_exc()
            self.log.warning(str(e))
            return False

    def add_handler(self, handler):
        self.handlers.append(handler)

    async def test_callback(self, event):
        self.handler_results = [
            handler.test_callback(self.mroom, event) for handler in self.handlers
        ]
        return any(self.handler_results)

    async def handle_callback(self, event):
        totrigger = compress(self.handlers, self.handler_results)
        for handler in totrigger:
            await handler.handle_callback(self.mroom, event)

    async def stop_all_tasks(self):
        await asyncio.gather(*(self.stop_task(t) for t in self.tasks))
        # TODO: Document destructor
        # TODO: change this to a register_destructor function callable by the
        # module
        if hasattr(self.module, "destructor") and callable(self.module.destructor):
            try:
                await self.module.destructor(self)
            except:
                pass
        # self.tasks = set()

    # =============================================
    # Plugin helpers (Command Handlers)
    # ==============================================
    class RegexHandler:
        """
        given a regex and a function, the function will be called,
        whenever a message matches the regex
        """

        def __init__(self, regexstring, handle_callback):
            self.re = re.compile(regexstring)
            self.handle_callback = handle_callback

        def test_callback(self, room, event):
            if event.source["type"] == "m.room.message":
                return self.re.match(event.source["content"]["body"])

    class CommandHandler(RegexHandler):
        """
        given a string s and a function, the function will be called,
        whenever !s is written at the start of a message
        """

        def __init__(self, commandstring, handle_callback):
            super().__init__(r"^!" + commandstring + "(\s.*)?$", handle_callback)

    # =============================================
    # Plugin helper functions (room)
    # ==============================================
    async def introduce_bot(self):
        await self.mroom.introduce_bot()

    async def send_html(self, formatted_txt, txt=""):
        response = await self.client.room_send(
            room_id=self.nio_room.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "format": "org.matrix.custom.html",
                "formatted_body": formatted_txt,
                "body": txt,
            },
            ignore_unverified_devices=True,
        )

    async def send_htmlnotice(self, formatted_txt, txt=""):
        response = await self.client.room_send(
            room_id=self.nio_room.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.notice",
                "format": "org.matrix.custom.html",
                "formatted_body": formatted_txt,
                "body": txt,
            },
            ignore_unverified_devices=True,
        )

    async def send_text(self, txt):
        await self.client.room_send(
            room_id=self.nio_room.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": txt,
            },
            ignore_unverified_devices=True,
        )

    async def send_notice(self, txt):
        await self.client.room_send(
            room_id=self.nio_room.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.notice",
                "body": txt,
            },
            ignore_unverified_devices=True,
        )



    async def _send_redirect_message(self, user_id):
        """
        Used in send_{text|html}_to_user to send an notice to look in the DMs for the response
        """
        await self.client.room_send(
            room_id=self.nio_room.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "format": "org.matrix.custom.html",
                "formatted_body": f"The response is confidential. {await self.format_user_highlight(user_id)} I'll send it to you in a private message",
                "body": "",
            },
            ignore_unverified_devices=True,
        )


    async def send_text_to_user(self, user_id, txt):
        await self.start_task(self.send_text_to_user_task(user_id, txt))

    async def send_text_to_user_task(self, user_id, txt):
        await self._send_redirect_message(user_id)
        room_id = await self.bot.get_private_room_with_user(user_id)
        await self.client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": f"Here is your private message from the room '{self.nio_room.display_name}'",
            },
            ignore_unverified_devices=True,
        )
        await self.client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": txt,
            },
            ignore_unverified_devices=True,
        )

    async def send_html_to_user(self, user_id, formatted_txt, txt=""):
        await self.start_task(self.send_html_to_user_task(user_id, formatted_txt, txt))

    async def send_html_to_user_task(self, user_id, formatted_txt, txt=""):
        await self._send_redirect_message(user_id)
        room_id = await self.bot.get_private_room_with_user(user_id)
        await self.client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": f"Here is your private message from the room '{self.nio_room.display_name}'",
            },
            ignore_unverified_devices=True,
        )
        await self.client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "format": "org.matrix.custom.html",
                "formatted_body": formatted_txt,
                "body": txt,
            },
            ignore_unverified_devices=True,
        )

    async def get_joined_members(self):
        """
        TODO: return right strings
        """
        k = await self.client.joined_members(self.nio_room.room_id)
        return k.members

    async def invite(self, user_id):
        await self.client.room_invite(self.nio_room.room_id, user_id)

    async def set_room_topic(self, description):
        """
        Updates the room description
        """
        res = await self.client.update_room_topic(self.nio_room.room_id, description)

    async def send_image(self, filename):
        p = pathlib.Path(filename)
        extension = p.suffix.lower()[1:]
        if extension not in ["gif", "png", "jpg", "jpeg"]:
            raise Exception(f"Unsupported image format: {extension}")
        mime = "image/{}".format(extension.replace("jpeg", "jpg"))
        uresp, fdi = await self.client.upload(
            lambda x, y: filename,
            content_type=mime,
            filename=p.name,
            encrypt=self.nio_room.encrypted,
        )
        if not type(uresp) == nio.UploadResponse:
            print("Unable to upload image")
        else:
            # TODO: add preview
            uri = uresp.content_uri
            c = {
                "msgtype": "m.image",
                "body": p.name,
                "info": {"mimetype": mime},  # can be extended
            }

            if self.nio_room.encrypted:
                c["mimetype"] = mime
                if fdi:
                    fdi["url"] = uri
                    fdi["mimetype"] = mime
                    c["file"] = fdi
                else:
                    c["file"] = {"url": uri, "mimetype": mime}
                # print(fdi)
            else:
                c["url"] = uri

            await self.client.room_send(
                room_id=self.nio_room.room_id,
                message_type="m.room.message",
                content=c,
                ignore_unverified_devices=True,
            )

    # =============================================
    # Plugin helper functions (key-value-store)
    # ==============================================
    # only use strings. Use json for conversion

    async def kvstore_get_plugin_keys(self):
        c = self.bot.conn.cursor()
        r = c.execute(
            """
            SELECT key
            FROM plugin_data
            WHERE pluginname=?;
            """,
            (self.pluginname,),
        )
        k = [k[0] for k in r.fetchall()]
        return k

    async def kvstore_get_room_keys(self):
        c = self.bot.conn.cursor()
        r = c.execute(
            """
            SELECT key
            FROM room_data
            WHERE roomid = ?;
            """,
            (self.mroom.room_id,),
        )
        k = [k[0] for k in r.fetchall()]
        return k

    async def kvstore_get_local_keys(self):
        c = self.bot.conn.cursor()
        r = c.execute(
            """
            SELECT key
            FROM room_plugin_data
            WHERE roomid = ? AND pluginname=?;
            """,
            (self.mroom.room_id, self.pluginname),
        )
        k = [k[0] for k in r.fetchall()]
        return k

    async def kvstore_get_plugin_value(self, key):
        c = self.bot.conn.cursor()
        r = c.execute(
            """
            SELECT value
            FROM plugin_data
            WHERE pluginname=? AND key=?;
            """,
            (self.pluginname, key),
        )
        k = r.fetchall()
        return k[0][0] if k else None

    async def kvstore_get_room_value(self, key):
        c = self.bot.conn.cursor()
        r = c.execute(
            """
            SELECT value
            FROM room_data
            WHERE roomid=? AND key=?;
            """,
            (self.mroom.room_id, key),
        )
        k = r.fetchall()
        return k[0][0] if k else None

    async def kvstore_get_local_value(self, key):
        c = self.bot.conn.cursor()
        r = c.execute(
            """
            SELECT value
            FROM room_plugin_data
            WHERE roomid=? AND pluginname=? AND key=?;
            """,
            (self.mroom.room_id, self.pluginname, key),
        )
        k = r.fetchall()
        return k[0][0] if k else None

    async def kvstore_set_plugin_value(self, key, value):
        c = self.bot.conn.cursor()
        r = c.execute(
            """
            INSERT OR REPLACE INTO plugin_data(pluginname,key,value)
            VALUES (?,?,?);
            """,
            (self.pluginname, key, value),
        )
        self.bot.conn.commit()

    async def kvstore_set_room_value(self, key, value):
        c = self.bot.conn.cursor()
        r = c.execute(
            """
            INSERT OR REPLACE INTO room_data(roomid,key,value)
            VALUES (?,?,?);
            """,
            (self.mroom.room_id, key, value),
        )
        self.bot.conn.commit()

    async def kvstore_set_local_value(self, key, value):
        c = self.bot.conn.cursor()
        r = c.execute(
            """
            INSERT OR REPLACE INTO room_plugin_data(roomid,pluginname,key,value)
            VALUES (?,?,?,?);
            """,
            (self.mroom.room_id, self.pluginname, key, value),
        )
        self.bot.conn.commit()

    async def kvstore_rem_plugin_value(self, key):
        c = self.bot.conn.cursor()
        r = c.execute(
            """
            DELETE FROM plugin_data
            WHERE pluginname=? AND key=?;
            """,
            (self.pluginname, key),
        )
        self.bot.conn.commit()

    async def kvstore_rem_room_value(self, key):
        c = self.bot.conn.cursor()
        r = c.execute(
            """
            DELETE FROM room_data
            WHERE roomid=? AND key=?;
            """,
            (self.mroom.room_id, key),
        )
        self.bot.conn.commit()

    async def kvstore_rem_local_value(self, key):
        c = self.bot.conn.cursor()
        r = c.execute(
            """
            DELETE FROM room_plugin_data
            WHERE roomid=? AND pluginname=? AND key=?
            """,
            (self.mroom.room_id, self.pluginname, key),
        )
        self.bot.conn.commit()

    # =============================================
    # Plugin helper functions (http_server)
    # ==============================================
    async def http_register_path(self, path, handler):
        """Registers a handler for a path. Returns the registered path
        e.g. for localhost/hallo/ -> hallo. None if path already has been registered.
        if the handler returns a aiohttp.web.Response, it will be forwarded to the http server
        otherwise a 200 is returned
        """
        return await self.bot.get_global_plugin_object("http_server").register_path(
            path, handler
        )

    async def http_deregister_path(self, path):
        """Deregisters a handler for a path. Returns the deregistered path
        e.g. for localhost/hallo/ -> hallo. None if path had not been registered."""
        return await self.bot.get_global_plugin_object("http_server").deregister_path(
            path
        )

    # =============================================
    # Plugin helper functions (tasks)
    # ==============================================
    async def start_repeating_task(self, f, interval=10, delay=0, cleanup=None):
        """
        run f every interval seconds with a beginning delay of delay seconds
        """

        async def run_every():
            try:
                await asyncio.sleep(delay)
                while True:
                    await f()
                    await asyncio.sleep(interval)
            except asyncio.CancelledError:
                if cleanup:
                    await cleanup()
                self.tasks.remove(t)
                raise asyncio.CancelledError

        t = asyncio.create_task(run_every())
        self.tasks.add(t)
        return t

    async def start_task(self, f):
        t = asyncio.create_task(f)
        self.tasks.add(t)
        return t

    async def stop_task(self, task):
        if not task.done():
            task.cancel()
        try:
            await asyncio.wait_for(task, 10)
        except asyncio.CancelledError:
            pass
        finally:
            if task in self.tasks:
                self.tasks.remove(task)

    # =============================================
    # Plugin helper functions (misc)
    # ==============================================
    async def format_user_highlight(self, user_id, display_name=None):
        """Format a hightlight to reference a user in a room. This message needs to be sent as html"""
        if display_name == None:
            display_name = (await self.client.get_displayname(user_id)).displayname
        return f'<a href="https://matrix.to/#/{user_id}">{display_name}</a>'

    @staticmethod
    def extract_args(event):
        return shlex.split(event.source["content"]["body"])

    @staticmethod
    def get_sender_id(event):
        return event.sender

    async def get_sender_name(self, event):
        return (await self.client.get_displayname(event.sender)).displayname
