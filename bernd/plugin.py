import nio
import asyncio
import logging
import importlib
import pathlib
import shlex

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
                self.module.register_to(self)
                return True
            except Exception as e:
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
        """
        TODO: change this architecture
        TODO: add try catch and print to room
        """
        self.handler_results = [handler.test_callback(self.mroom, event) for handler in self.handlers]
        print(self.handlers)
        return any(self.handler_results)
    
    async def handle_callback(self, event):
        """
        TODO: add try catch and print to room
        """
        totrigger = compress(self.handlers,self.handler_results)
        for handler in totrigger:
            await handler.handle_callback(self.mroom, event)


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
        #print(f"{mime=}")
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
    # Plugin helper functions (misc)
    #==============================================
    @staticmethod
    def extract_args(event):
        return shlex.split(event.source['content']['body'])
