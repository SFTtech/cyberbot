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
    def __init__(self, mroom, pluginid, pluginname):
        self.pluginid = pluginid
        self.pluginname = pluginname
        self.handlers = []
        self.module = None
        self.mroom = mroom
        self.nio_room = mroom.nio_room
        self.bot = mroom.bot
        self.client = mroom.bot.client

        self.tasks = set()

    async def load(self):
        filename = self.pluginname + "_plugin.py"
        plugin_path = Path(self.mroom.bot.plugindir).resolve()
        logging.info(f"Room {self.mroom.nio_room.room_id}: trying to load {plugin_path / filename}")
        if (plugin_path / filename).exists():
            modname = f'plugins.{self.pluginname}'
            loader = importlib.machinery.SourceFileLoader(modname,
                    str(plugin_path/filename))
            try:
                self.module = loader.load_module(modname)
                self.module.ENVIRONMENT = self.mroom.bot.environment.copy()
                await self.module.register_to(self)
                return True
            except Exception as e:
                traceback.print_exc()
                logging.warning(str(e))
                return False
        else:
            logging.warning(f"""
            Room {self.mroom.room_id}: couldn't load plugin {self.pluginname}: file does not exist
            """)
            return False

    def add_handler(self, handler):
        self.handlers.append(handler)

    async def test_callback(self, event):
        self.handler_results = [handler.test_callback(self.mroom, event) for handler in self.handlers]
        return any(self.handler_results)
    
    async def handle_callback(self, event):
        totrigger = compress(self.handlers,self.handler_results)
        for handler in totrigger:
            await handler.handle_callback(self.mroom, event)

    async def stop_all_tasks(self):
        await asyncio.gather(*(self.stop_task(t) for t in self.tasks))
        # TODO: Document destructor
        # TODO: change this to a register_destructor function callable by the
        # module
        if hasattr(self.module,"destructor") and callable(self.module.destructor):
            try:
                await self.module.destructor(self)
            except:
                pass
        #self.tasks = set()




    #=============================================
    # Plugin helpers (Command Handlers)
    #==============================================
    class RegexHandler:
        """
        given a regex and a function, the function will be called,
        whenever a message matches the regex
        """
        def __init__(self, regexstring, handle_callback):
            self.re = re.compile(regexstring)
            self.handle_callback = handle_callback

        def test_callback(self, room, event):
            if event.source['type'] == 'm.room.message':
                return self.re.match(event.source['content']['body'])

    class CommandHandler(RegexHandler):
        """
        given a string s and a function, the function will be called,
        whenever !s is written at the start of a message
        """
        def __init__(self, commandstring, handle_callback):
            super().__init__(r'^!' + commandstring + '(\s.*)?$', handle_callback)


    #=============================================
    # Plugin helper functions (room)
    #==============================================
    async def introduce_bot(self):
        await self.mroom.introduce_bot()

    async def send_html(self, formatted_txt, txt=""):
        response = await self.client.room_send(
                room_id=self.nio_room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "format": "org.matrix.custom.html",
                    "formatted_body" : formatted_txt,
                    "body": txt,
                },
                ignore_unverified_devices=True)
        logging.debug(response)

    async def send_text(self, txt):
        await self.client.room_send(
                room_id=self.nio_room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": txt,
                },
                ignore_unverified_devices=True)

    async def send_notice(self, txt):
        await self.client.room_send(
                room_id=self.nio_room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.notice",
                    "body": txt,
                },
                ignore_unverified_devices=True)

    async def get_joined_members(self):
        """
        TODO: return right strings
        """
        k = await self.client.joined_members(self.nio_room.room_id)
        return k.members


    async def send_image(self, filename):
        p = pathlib.Path(filename)
        extension = p.suffix.lower()[1:]
        if extension not in ["gif", "png", "jpg", "jpeg"]:
            raise Exception(f"Unsupported image format: {extension}")
        mime = "image/{}".format(extension.replace("jpeg", "jpg"))
        uresp,fdi = await self.client.upload(lambda x,y: filename,
                content_type=mime,
                filename=p.name,
                encrypt=self.nio_room.encrypted)
        if not type(uresp) == nio.UploadResponse:
            print("Unable to upload image")
        else:
            # TODO: add preview
            uri = uresp.content_uri
            c = {
                    "msgtype": "m.image",
                    "body": p.name,
                    "info" : {"mimetype" : mime} # can be extended
                }

            if self.nio_room.encrypted:
                c["mimetype"]  = mime
                if fdi:
                    fdi["url"] = uri
                    fdi["mimetype"] = mime
                    c["file"] = fdi
                else:
                    c["file"] = {"url" : uri, "mimetype" : mime}
                #print(fdi)
            else:
                c["url"] = uri

            await self.client.room_send(
                    room_id=self.nio_room.room_id,
                    message_type="m.room.message",
                    content=c,
                    ignore_unverified_devices=True)


    #=============================================
    # Plugin helper functions (key-value-store)
    #==============================================
    # only use strings. Use json for conversion
    async def kvstore_get_keys(self):
        c = self.bot.conn.cursor()
        r = c.execute("""
        SELECT key
        FROM plugin_data
        WHERE pluginid=?;
        """, (self.pluginid,))
        k = [k[0] for k in r.fetchall()]
        return k

    async def kvstore_get_value(self, key):
        c = self.bot.conn.cursor()
        r = c.execute("""
        SELECT value
        FROM plugin_data
        WHERE pluginid=? and key=?;
        """, (self.pluginid,key))
        k = r.fetchall()
        return k[0][0] if k else None

    async def kvstore_set_value(self, key, value):
        c = self.bot.conn.cursor()
        r = c.execute("""
        INSERT OR REPLACE INTO plugin_data(pluginid,key,value)
        VALUES (?,?,?)
        """, (self.pluginid,key,value))
        self.bot.conn.commit()
    
    async def kvstore_rem_value(self, key):
        c = self.bot.conn.cursor()
        r = c.execute("""
        DELETE FROM plugin_data
        WHERE pluginid=? and key=?
        """, (self.pluginid,key))
        self.bot.conn.commit()


    #=============================================
    # Plugin helper functions (tasks)
    #==============================================
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


    async def start_task(f):
        t = asyncio.create_task(f)
        self.tasks.add(t)
        return t


    async def stop_task(self, task):
        if not task.done():
            task.cancel()
        try:
            await asyncio.wait_for(task,10)
        except asyncio.CancelledError:
            pass
        finally:
            if task in self.tasks:
                self.tasks.remove(task)


    #=============================================
    # Plugin helper functions (misc)
    #==============================================
    @staticmethod
    def extract_args(event):
        return shlex.split(event.source['content']['body'])
