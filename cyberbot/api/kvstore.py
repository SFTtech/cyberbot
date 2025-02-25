from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .database import Database


class KVStore:
    """
    a persistent key-value store.

    supports the following realms:
    - for a plugin and a room  (try to use this)
    - for a plugin             (for sharing across rooms)
    - for a room               (for sharing across plugins)
    """

    def __init__(self, db: Database, plugin_name: str, room_id: str):
        self._db = db
        self._plugin_name = plugin_name
        self._room_id = room_id

    async def keys(self, room: bool = True, plugin: bool = True):
        if not (room or plugin):
            raise RuntimeError('either per-room or per-plugin scope must be set')

        qwhere = list()
        args = list()

        if room:
            table = "room_data"
            qwhere.append('roomid=?')
            args.append(self._room_id)

        if plugin:
            table = "plugin_data"
            qwhere.append('pluginname=?')
            args.append(self._plugin_name)

        if room and plugin:
            table = "room_plugin_data"

        ret = self._db.read(
            f"select key from {table} where {' and '.join(qwhere)};",
            args,
        )
        keys = [row[0] for row in ret.fetchall()]
        return keys

    async def get(self, key: str, room: bool = True, plugin: bool = True) -> str | None:
        if not (room or plugin):
            raise RuntimeError('either per-room or per-plugin scope must be set')

        qwhere = list()
        args = list()

        qwhere.append('key=?')
        args.append(key)

        if room:
            table = "room_data"
            qwhere.append('roomid=?')
            args.append(self._room_id)

        if plugin:
            table = "plugin_data"
            qwhere.append('pluginname=?')
            args.append(self._plugin_name)

        if room and plugin:
            table = "room_plugin_data"

        cur = self._db.read(
            f"select value from {table} where {' and '.join(qwhere)};",
            args,
        )
        ret = cur.fetchone()
        if ret:
            return ret[0]

        return None

    async def set(self, key: str, value: str, room: bool = True, plugin: bool = True):
        if not (room or plugin):
            raise RuntimeError('either per-room or per-plugin scope must be set')

        args = [key, value]
        set_rows = ['key', 'value']

        if room:
            table = "room_data"
            set_rows.append('roomid')
            args.append(self._room_id)

        if plugin:
            table = "plugin_data"
            set_rows.append('pluginname')
            args.append(self._plugin_name)

        if room and plugin:
            table = "room_plugin_data"

        ret = self._db.write(
            f"insert or replace into {table}({', '.join(set_rows)}) values ({','.join('?' * len(args))});",
            args,
        )
        return ret

    async def rm(self, key: str, room: bool = True, plugin: bool = True):
        if not (room or plugin):
            raise RuntimeError('either per-room or per-plugin scope must be set')

        args = [key]
        qwhere = ['key=?']

        if room:
            table = "room_data"
            qwhere.append('roomid=?')
            args.append(self._room_id)

        if plugin:
            table = "plugin_data"
            qwhere.append('pluginname=?')
            args.append(self._plugin_name)

        if room and plugin:
            table = "room_plugin_data"

        ret = self._db.write(
            f"delete from {table} where {' and '.join(qwhere)};",
            args,
        )
        return ret
