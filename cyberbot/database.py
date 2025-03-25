import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, path: Path):
        self._dbpath = path
        self._connection: sqlite3.Connection = sqlite3.connect(path, autocommit=False)
        self._connection.execute("PRAGMA foreign_keys = ON;")

    def cursor(self) -> sqlite3.Cursor:
        return self._connection.cursor()

    def read(self, sql, params={}) -> sqlite3.Cursor:
        logger.debug("reading sql: %s <- %s", sql, params)
        ret = self._connection.execute(sql, params)
        if self._connection.in_transaction:
            self._connection.rollback()
        return ret

    def write(self, sql, params={}) -> sqlite3.Cursor:
        logger.debug("writing sql: %s <- %s", sql, params)
        ret = self._connection.execute(sql, params)
        self._connection.commit()
        return ret

    def write_many(self, sql, paramlist=[]) -> sqlite3.Cursor:
        logger.debug("writing-many sql: %s <- %s", sql, paramlist)
        ret = self._connection.executemany(sql, paramlist)
        self._connection.commit()
        return ret

    def migrate(self):
        """
        transform the database schema to the latest version.
        """
        c = self._connection.cursor()

        c.executescript(
            """
            -- store temporary tables in memory only
            pragma temp_store = MEMORY;

            -- room_plugins: which plugins are activated in which room
            create table if not exists room_plugins (
                roomid     text,
                pluginname text,
                primary key (roomid, pluginname)
            ) strict;

            -- global room data
            create table if not exists room_data (
                roomid     text,
                key        text,
                value      text,
                primary key (roomid, key)
            ) strict;

            -- plugin_data: global plugin data
            create table if not exists plugin_data (
                pluginname text,
                key        text,
                value      text,
                primary key (pluginname, key)
            ) strict;

            -- data local to a plugin x room combination
            create table if not exists room_plugin_data (
                roomid     text,
                pluginname text,
                key        text,
                value      text,
                primary key (roomid, pluginname, key)
            ) strict;

            -- global bot information such as login token
            create table if not exists state (
                key   text primary key,
                value text
            ) strict;

            -- mapping of interaction rooms and its config rooms
            create table if not exists config_room (
                source_roomid text,
                target_roomid text
            ) strict;
            create index if not exists idx_config_rooms_source_roomid on config_room(source_roomid);
            create index if not exists idx_config_rooms_target_roomid on config_room(target_roomid);
            create unique index if not exists uidx_config_rooms_source_target_roomid
                on config_room(source_roomid, target_roomid);

            -- who may configure which room
            create table if not exists config_acl (
                roomid text primary key,
                acl text
            ) strict;
            """
        )
        self._connection.commit()
