"""
access control lists for a room
"""

from __future__ import annotations

import enum
import json
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Generator

    from .bot import Bot


class Role(enum.StrEnum):
    config = enum.auto()


class _ACL:
    """
    acl specification for a room
    """

    def __init__(self, text: str | None):
        # {user -> {role, ...}}
        self.user: dict[str, set[str]] = dict()
        # {min_level -> {role, ...}}  # which room level may configure
        self.level: dict[int, set[str]] = dict()

        if text is not None:
            try:
                raw_entries = json.loads(text)
            except json.JSONDecodeError as e:
                raise ValueError("failed to json-decode room acl") from e

            for user, privs in raw_entries["user"].items():
                self.user[user] = set(privs)

            for min_level, privs in raw_entries["level"].items():
                self.level[int(min_level)] = set(privs)

    def dump(self):
        out = {
            "user": {user: list(privs) for user, privs in self.user.items()},
            "level": {str(level): list(privs) for level, privs in self.level.items()},
        }
        return json.dumps(out)

    def user_role_add(self, user_id: str, role: Role):
        privs = self.user.setdefault(user_id, set())
        privs.add(role)

    def user_role_remove(self, user_id: str, role: Role):
        privs = self.user.get(user_id)
        if privs:
            privs.discard(role)

    def level_role_add(self, min_level: int, role: Role):
        privs = self.level.setdefault(min_level, set())
        privs.add(role)

    def level_role_remove(self, min_level: int, role: Role):
        privs = self.level.get(min_level)
        if privs:
            privs.discard(role)

    def is_allowed(
        self, role: Role, user_id: str | None = None, level: int | None = None
    ) -> bool:
        if user_id is None and level is None:
            raise ValueError("either userid or level needed")

        if user_id is not None:
            user_privs = self.user.get(user_id)

            if user_privs and role in user_privs:
                return True

        if level is not None:
            for level_nr, level_privs in self.level.items():
                # collect all privileges applicable for the current user
                if level_nr <= level:
                    if role in level_privs:
                        return True

        return False

    def show(self) -> str:
        return f"users: {self.user}\nlevels: {self.level}"


class RoomACL:
    """
    manage the acl of a room.
    """

    def __init__(self, bot: Bot, room_id: str):
        self._bot: Bot = bot
        self._room_id: str = room_id
        self._changed: bool = False
        self._acl: _ACL | None = None

    def __enter__(self) -> RoomACL:
        acl_raw = self._bot.db.read(
            "select acl from config_acl where roomid=?", (self._room_id,)
        ).fetchone()
        if acl_raw:
            acl_raw = acl_raw[0]
        self._acl = _ACL(acl_raw)
        return self

    def __exit__(self, type, exc_value, traceback):
        if self._changed and exc_value is None:
            # only commit if we changed something
            # and there no exception
            self._commit()
        self._acl = None

    def _commit(self):
        if self._acl is None:
            raise RuntimeError("missing acl data due to missing 'with room.acl'")

        self._bot.db.write(
            "insert or replace into config_acl(roomid, acl) values (?, ?);",
            (self._room_id, self._acl.dump()),
        )
        self._acl = None

    @contextmanager
    def _get_acl(self, change: bool=False) -> Generator[_ACL]:
        """
        just get the _ACL handle,
        and set remember if it changed after adjustments.
        """
        if self._acl is None:
            raise RuntimeError("acl has not been read from db yet - use 'with room.acl' statement")
        try:
            yield self._acl
        finally:
            if change:
                self._changed = True

    def show(self) -> str:
        with self._get_acl() as acl:
            return acl.show()

    def user_has_role(self,
                      role_name: str,
                      user_id: str | None = None,
                      user_level: int | None = None) -> bool:
        with self._get_acl() as acl:
            if user_id and self._bot.is_admin(user_id):
                return True

            role: Role = Role(role_name)

            return acl.is_allowed(role, user_id=user_id, level=user_level)

    #####
    # ACL adjustments
    def user_role_add(self, user_id: str, role_name: str):
        with self._get_acl(change=True) as acl:
            role: Role = Role(role_name)
            acl.user_role_add(user_id, role)

    def user_role_remove(self, user_id: str, role_name: str):
        with self._get_acl(change=True) as acl:
            role: Role = Role(role_name)
            acl.user_role_add(user_id, role)

    def user_roles_clear(self, user_id: str):
        with self._get_acl(change=True) as acl:
            for role in Role:
                acl.user_role_remove(user_id, role)

    def level_role_add(self, level: int, role_name: str):
        with self._get_acl(change=True) as acl:
            role: Role = Role(role_name)
            acl.level_role_remove(level, role)

    def level_role_remove(self, level: int, role_name: str):
        with self._get_acl(change=True) as acl:
            role: Role = Role(role_name)
            acl.level_role_remove(level, role)

    def level_roles_clear(self, level: int):
        with self._get_acl(change=True) as acl:
            for role in Role:
                acl.level_role_remove(level, role)
