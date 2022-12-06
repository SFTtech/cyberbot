import asyncio
import nio
import logging
import importlib

from itertools import compress

from plugin import Plugin

nio.RoomMember.get_friendly_name = lambda self: self.display_name

# just a reminder to think of synchronization and race conditions
# every yield, return and await represents a point where control
# flow can be interrupted.

class MatrixRoom():

    def __init__(self, matrixbot, nio_room):
        self.bot = matrixbot
        self.nio_room = nio_room
        self.room_id = nio_room.room_id
        self.client = matrixbot.client
        self.plugins = []
        self.log = logging.getLogger(f"{__name__}.{self.room_id}")


    def __str__(self):
        return f"Matrix Room: {self.room_id}"

    async def load_plugins(self):
        self.log.info("Loading Plugins for Room")
        c = self.bot.conn.cursor()
        r = c.execute("""
        SELECT pluginname
        FROM rooms JOIN room_plugins ON rooms.roomid == room_plugins.roomid
        WHERE rooms.roomid=?;
        """, (self.room_id,))

        for (pname,) in r.fetchall():
            self.plugins.append(Plugin(self, pname))

        # load plugins
        results = await asyncio.gather(*(p.load() for p in self.plugins))
        self.plugins = list(compress(self.plugins,results))


    async def handle_text_event(self, event):
        results = await asyncio.gather(*(p.test_callback(event)
            for p in self.plugins))
        await asyncio.gather(*(p.handle_callback(event)
            for p in compress(self.plugins,results)))


    async def introduce_bot(self):
        try:
            self.log.info(f"Introducing myself to {self.room_id}")
            txt = f"""Hi, my name is {self.bot.botname}! I was just (re)started. Type !help to see my (new) capabilities."""
            await self.client.room_send(
                    room_id=self.room_id,
                    message_type="m.room.message",
                    content={
                        "msgtype": "m.text",
                        "body": txt,
                    },
                    ignore_unverified_devices=True)
        except Exception as e:
            self.log.info(f"Exception: {e}")

    @classmethod
    async def new(cls, bot, nio_room):
        """
        To be called on entering a new room. Acts as a constructor for MatrixRoom and adds
        the room to the database among introducing itself to the room.
        """
        c = bot.conn.cursor()
        # this is a "insert if not already exists"
        r = c.execute("""
        INSERT INTO rooms
        SELECT (?)
        WHERE NOT EXISTS (SELECT * FROM rooms
                          WHERE roomid = ?);
        """, (nio_room.room_id,nio_room.room_id,))
        bot.conn.commit()

        room = cls(bot, nio_room)
        await room.load_plugins()
        await room.bot.client.sync()
        await room.introduce_bot()
        for p in ["help", "meta"]:
            if not any(p == plugin.pluginname for plugin in room.plugins):
                await room.add_plugin(p)
        return room

    async def add_plugin(self, pluginname):
        # TODO show error in chat
        if not pluginname in self.bot.available_plugins:
            self.log.warning(f"tried to load invalid plugin {pluginname}")
            return
        if pluginname in [p.pluginname for p in self.plugins]:
            self.log.warning(f"tried to load already loaded plugin {pluginname}")
            return
        c = self.bot.conn.cursor()
        r = c.execute("""
        INSERT INTO room_plugins(roomid,pluginname)
        VALUES (?,?); 
        """, (self.room_id, pluginname))
        self.bot.conn.commit()
        self.log.info(f"Adding plugin {pluginname} to room")
        plugin = Plugin(self, pluginname)
        self.plugins.append(plugin)
        # this has to be the last statement to prevent race conditions
        await plugin.load()

    async def remove_plugin(self, pluginname):
        self.log.info(f"Removing plugin {pluginname} from room")
        # no need for lock as only yielding point of control flow is await statement, which is last
        c = self.bot.conn.cursor()
        # we put this before the if block to be able to remove plugins that are left by accident
        r = c.execute("""
        DELETE FROM room_plugins
        WHERE roomid=? AND pluginname=?;
        """, (self.room_id, pluginname))
        self.bot.conn.commit()
        indices = [i for (i,p) in enumerate(self.plugins) if p.pluginname==pluginname]
        if indices:
            p = self.plugins[indices[0]]
            del self.plugins[indices[0]]
            await p.stop_all_tasks()
