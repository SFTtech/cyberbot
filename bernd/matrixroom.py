import asyncio
import nio
import pathlib
import logging
import importlib

from itertools import compress
from pathlib import Path

from plugin import Plugin

nio.RoomMember.get_friendly_name = lambda self: self.display_name


class MatrixRoom():

    async def load_plugins(self):
        c = self.bot.conn.cursor()
        r = c.execute("""
        SELECT pluginid,pluginname
        FROM rooms JOIN room_plugins ON rooms.roomid == room_plugins.roomid
        WHERE rooms.roomid=?;
        """, (self.room_id,))

        # construct plugins
        self.plugins = []
        for pid,pname in r.fetchall():
            self.plugins.append(Plugin(self,pid,pname))

        # load plugins
        results = await asyncio.gather(*(p.load() for p in self.plugins))
        self.plugins = list(compress(self.plugins,results))


    async def handle_text_event(self, event):
        results = await asyncio.gather(*(p.test_callback(event)
            for p in self.plugins))
        await asyncio.gather(*(p.handle_callback(event)
            for p in compress(self.plugins,results)))


    def __init__(self, matrixbot, nio_room):
        self.bot = matrixbot
        self.nio_room = nio_room
        self.room_id = nio_room.room_id
        self.client = matrixbot.client


    async def introduce_bot(self):
        try:
            logging.info(f"Introducing myself to {self.nio_room.room_id}")
            txt = f"""Hi, my name is {self.bot.botname}! I was just (re)started. Type !help to see my (new) capabilities."""
            await self.client.room_send(
                    room_id=self.nio_room.room_id,
                    message_type="m.room.message",
                    content={
                        "msgtype": "m.text",
                        "body": txt,
                    },
                    ignore_unverified_devices=True)
        except Exception as e:
            logging.info(f"Exception: {e}")

    @classmethod
    async def new(cls, bot, nio_room):
        """
        call this when bot enters a new room
        """
        c = bot.conn.cursor()
        r = c.execute("""
        INSERT INTO rooms
        SELECT (?)
        WHERE NOT EXISTS (SELECT * FROM rooms
                          WHERE roomid = ?);
        """, (nio_room.room_id,nio_room.room_id,))
        bot.conn.commit()

        room = cls(bot, nio_room)
        await room.load_plugins()
        await room.introduce_bot()
        for p in ["help", "meta"]:
            if not any(p == plugin.pluginname for plugin in room.plugins):
                await room.add_plugin(p)
        return room

    async def add_plugin(self, pluginname):
        if not pluginname in self.bot.available_plugins:
            logging.warning(f"{self.room_id} tried to load invalid plugin {pluginname}")
            return
        c = self.bot.conn.cursor()
        r = c.execute("""
        INSERT INTO room_plugins(roomid,pluginname)
        VALUES (?,?); 
        """, (self.room_id, pluginname))
        self.bot.conn.commit()
        r = c.execute("""
        SELECT last_insert_rowid();
        """)
        (pid,), = r.fetchall()

        plugin = Plugin(self,pid,pluginname)
        await plugin.load()
        self.plugins.append(plugin)

    async def remove_plugin(self, pluginname):
        c = self.bot.conn.cursor()
        indizes = [i for (i,p) in enumerate(self.plugins) if p.pluginname==pluginname]
        if indizes:
            r = c.execute("""
            DELETE FROM room_plugins
            WHERE roomid=? AND pluginname=?;
            """, (self.room_id, pluginname))
            self.bot.conn.commit()
            await self.plugins[indizes[0]].stop_all_tasks()
            del self.plugins[indizes[0]]
