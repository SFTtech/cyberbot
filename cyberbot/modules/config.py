from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cyberbot.api.room_plugin import RoomAPI, RoomPlugin
from cyberbot.api.text_handler import CLIHandler, CommandParser, Err, MessageText, Ok, Result
from cyberbot.room_acl import Role

if TYPE_CHECKING:
    from argparse import Namespace

    from cyberbot.api.room_api import Room
    from cyberbot.api.room_plugin import PluginConfigParser


# roles available for configuration
roles: list[str] = [val.value for val in Role] + ["none"]


@dataclass
class Issuer:
    """
    configuration commands are issued by a user, which has a permission power level.
    """
    user_id: str
    power_level: int


class Config(RoomPlugin):
    """
    control configuration for rooms and plugins.

    This plugin will only activate in config-rooms!
    `Room.init()` explicitly loads it then.

    Privileges in config room:
      - by default just initial inviter of the bot in a room.
      - one can name other users or admins/mods/power level

    TODO: Shared config rooms:
      - `configroom create shared` for a selected room - all allowed users are invited then.
      - configuration for that room only possible in the shared room then
      - one can invite other users and they are allowed then
      - when somebody new joins a INTERACTION room
        -> nothing happens, except they have/gain acl privileges
        -> then are invited to config room
      - if privileges, but not in that room, can ask bot to be invite to the shared room (again)
    """

    @classmethod
    def about(cls) -> str:
        return "configuration of room modules and acl"

    def __init__(self, api: RoomAPI):
        self._api = api
        self._room_plugin_config_parsers: dict[str, PluginConfigParser] = dict()

    async def init(self) -> None:
        self._cli_parser: CLIHandler | None = None

        target_room = await self._get_selected_target_room()
        # build ArgumentParser
        self._update_cli(target_room)

        # update room title with current target room
        await self._update_room_topic(target_room)

    def _get_parser(
        self,
        target_room: Room | None = None,
    ) -> CommandParser:

        cli = CommandParser(prog="<config>")
        sp = cli.add_subparsers(dest="mode", required=True)

        # help
        _help_cli = sp.add_parser("help")

        #- room
        room_cli = sp.add_parser("room")
        room_sp = room_cli.add_subparsers(dest="room_action", required=True)

        #-- room list
        list_cli = room_sp.add_parser("list")

        #-- room select <room_id>
        select_cli = room_sp.add_parser("select")
        select_cli.add_argument("room_id")

        #-- room create
        create_cli = room_sp.add_parser("create")
        create_cli.add_argument("--preset", choices=["public", "private", "trusted_private"], default="public")
        create_cli.add_argument("title", nargs="+")

        #-- room invite
        room_invite_cli = room_sp.add_parser("invite")
        room_invite_cli.add_argument("user")

        #-- room acl
        acl_cli = room_sp.add_parser("acl")
        acl_sp = acl_cli.add_subparsers(dest="acl_action", required=True)

        #--- room acl show
        _acl_show_cli = acl_sp.add_parser("show")

        #--- room acl set-role <username> <role>
        # set-role only works if issuing role is owner
        acl_setrole_cli = acl_sp.add_parser("set-role")
        acl_setrole_cli.add_argument("username")
        acl_setrole_cli.add_argument("role", choices=roles)

        #--- room acl remove-role <username> <role>
        acl_removerole_cli = acl_sp.add_parser("remove-role")
        acl_removerole_cli.add_argument("username")
        acl_removerole_cli.add_argument("role", choices=roles)

        #--- room acl set-level-role <level> <role>
        acl_setlevel_cli = acl_sp.add_parser("set-level-role")
        acl_setlevel_cli.add_argument("level", type=int)
        acl_setlevel_cli.add_argument("role", choices=roles)

        #--- room acl remove-level-role <level> <role>
        acl_removelevel_cli = acl_sp.add_parser("remove-level-role")
        acl_removelevel_cli.add_argument("level", type=int)
        acl_removelevel_cli.add_argument("role", choices=roles)

        #-- room configroom
        configroom_cli = room_sp.add_parser("configroom")
        configroom_sp = configroom_cli.add_subparsers(
            dest="configroom_action", required=True
        )
        #--- room configroom create <separate|shared>: creates shared config room for currently selected room
        configroom_create_cli = configroom_sp.add_parser("create")
        configroom_create_cli.add_argument("variant", choices=["split", "shared"])

        #--- room configroom re-invite <user>|self: invites user to the config room if has config role
        configroom_reinvite_cli = configroom_sp.add_parser("re-invite")
        configroom_reinvite_cli.add_argument("user")

        #-- room plugin
        plugin_cli = room_sp.add_parser("plugin")
        plugin_sp = plugin_cli.add_subparsers(dest="action", required=True)

        #--- room plugin activate <name>
        activate_cli = plugin_sp.add_parser("activate")
        activate_cli.add_argument("name")

        #--- room plugin remove <name>
        remove_cli = plugin_sp.add_parser("remove")
        remove_cli.add_argument("name")

        #--- room plugin list [--all]
        list_cli = plugin_sp.add_parser("list")
        list_cli.add_argument("--all", action="store_true")

        #--- room plugin config <plugin_name> <what>
        if target_room is not None:
            configurable_plugins: dict[str, RoomPlugin] = target_room.get_plugins()
            self._room_plugin_config_parsers = dict()

            if configurable_plugins:
                plugin_config_cli = plugin_sp.add_parser("config")
                pcfg_cli = plugin_config_cli.add_subparsers(dest="plugin_name", required=True)

                for plugin_name, plugin in configurable_plugins.items():
                    plugin_cli = pcfg_cli.add_parser(plugin_name)
                    eval_func = plugin.config_setup(plugin_cli)
                    if eval_func:
                        self._room_plugin_config_parsers[plugin_name] = eval_func

        return cli

    async def _send_block(self, text):
        block = self._api.format_code(text)
        return await self._api.send_html(block, notice=True)

    async def _send_notice(self, text):
        return await self._api.send_notice(text)

    async def _on_message(
        self,
        result: Result[Namespace, str],
        event: MessageText,
        parser: CommandParser,
    ):
        """
        commands:
        - room
          select which room to configure.
          this is important for config rooms, so one can choose which room the module config is for.

        - plugin
          modify and configure active plugins
        """

        match result:
            case Err(msg):
                # return arg error
                await self._send_block(msg)
                return
            case Ok(arguments):
                args = arguments

        issuer_user_name = event.sender
        issuer_level = await self._api.get_user_power_level(issuer_user_name)
        issuer = Issuer(issuer_user_name, issuer_level)

        try:
            await self._cmd(issuer, args, parser)

        except ValueError as err:
            await self._send_notice(str(err))

        except Exception:
            await self._send_notice("internal error")
            raise

    async def _cmd(self, issuer: Issuer, args: Namespace, parser: CommandParser):
        """
        evaluate and run the bot commands
        """
        match args.mode:
            case "help":
                await self._send_block(parser.format_help())

            case "room":
                await self._cmd_room(issuer, args, parser)

            case _:
                raise NotImplementedError(f"unknown cmd mode {args.mode!r}")

    async def _cmd_room(self, issuer: Issuer, args: Namespace, parser: CommandParser) -> None:
        """
        commands to select, configure, create, change rooms.
        """

        match args.room_action:
            case "list":
                rooms = await self._api.get_config_target_rooms()
                if rooms:
                    lines = ["configurable rooms:"]
                    maxroom = max(len(name) for name in rooms.keys())
                    for room_id, room in rooms.items():
                        lines.append(f"{room_id.ljust(maxroom)} {room.display_name}")
                    await self._send_block("\n".join(lines))
                else:
                    await self._send_notice("no rooms available for configuration")
                    return

            case "select":
                selected = args.room_id
                if not (selected.startswith("!") or ":" in selected):
                    raise ValueError(
                        "invalid room id, must have form !lol42:server.rofl"
                    )

                await self._set_selected_target_room(issuer, selected)
                return

            case "create":
                title = " ".join(args.title)
                new_room = await self._api.create_room(creator=issuer.user_id, name=title, preset=args.preset)
                await self._set_selected_target_room(issuer, new_room.room_id)
                return

            case _:
                target_room: Room | None = await self._get_selected_target_room()
                if target_room is None:
                    await self._send_notice("no room selected to operate on")
                    return

                with target_room.acl as acl:
                    if not acl.user_has_role(Role.config, user_id=issuer.user_id, user_level=issuer.power_level):
                        await self._send_notice("you're not allowed to configure this room")
                        return

                match args.room_action:
                    case "invite":
                        match await target_room.invite(args.user):
                            case Err(msg):
                                await self._send_notice(f"failed: {msg}")
                            case _:
                                await self._send_notice("invite success.")
                        return

                    case "acl":
                        match args.acl_action:
                            case "show":
                                with target_room.acl as acl:
                                    await self._send_block(acl.show())

                            case "set-role":
                                with target_room.acl as acl:
                                    if args.role == "none":
                                        acl.user_roles_clear(args.username)
                                    else:
                                        acl.user_role_add(args.username, args.role)

                            case "remove-role":
                                if args.role == "none":
                                    await self._send_notice(f"role {args.role!r} must be set, not removed.")
                                    return

                                with target_room.acl as acl:
                                    acl.user_role_remove(args.username, args.role)

                            case "set-level-role":
                                with target_room.acl as acl:
                                    if args.role == "none":
                                        acl.level_roles_clear(args.level)
                                    else:
                                        acl.level_role_add(args.level, args.role)

                            case "remove-level-role":
                                if args.role == "none":
                                    await self._send_notice(f"role {args.role!r} must be set, not removed.")
                                    return

                                with target_room.acl as acl:
                                    acl.level_role_remove(args.level, args.role)

                            case _:
                                raise NotImplementedError()
                        return

                    case "configroom":
                        match args.configroom_action:
                            case "create":
                                # args.variant  # split|shared
                                raise NotImplementedError()

                            case "re-invite":
                                # args.user
                                raise NotImplementedError()

                            case _:
                                raise NotImplementedError()
                        return

                    case "plugin":
                        await self._cmd_room_plugin(issuer, args, parser)
                        return

                    case _:
                        raise NotImplementedError(f"unhandled {args.room_action}")

    async def _cmd_room_plugin(self, issuer: Issuer, args: Namespace, parser: CommandParser):
        target_room = await self._get_selected_target_room()
        if target_room is None:
            await self._send_notice("no room selected to operate on")
            return

        with target_room.acl as acl:
            if not acl.user_has_role(Role.config,
                                     user_id=issuer.user_id,
                                     user_level=issuer.power_level):
                await self._send_notice("you're not allowed to configure this room")
                return

        match args.action:
            case "activate":
                result = await target_room.activate_plugin(args.name)
                await self._send_block(str(result))
                self._update_cli(target_room)

            case "remove":
                result = await target_room.remove_plugin(args.name)
                await self._send_block(str(result))
                self._update_cli(target_room)

            case "list":
                active_plugins = target_room.get_plugins().keys()
                if args.all:
                    plugins = await self._api.get_available_plugins()
                    if plugins:
                        maxlen = max((len(k) for k in plugins.keys()))
                        plugin_desc = [f"[{'x' if plugin_name in active_plugins else ' '}] "
                                       f"{plugin_name.ljust(maxlen)} - {mod.about()}"
                                       for plugin_name, mod in sorted(plugins.items())]
                        await self._send_block(
                            f"available plugins:\n{'\n'.join(plugin_desc)}"
                        )
                    else:
                        await self._send_block("no available plugins")

                elif active_plugins:
                    await self._send_block(
                        f"active plugins:\n{'\n'.join(sorted(active_plugins))}"
                    )
                else:
                    await self._send_block("no active plugins, use --all to see available.")

            case "config":
                config_parser: PluginConfigParser = self._room_plugin_config_parsers[args.plugin_name]
                # call to the remote plugin, and let it answer through our room api.
                await config_parser(args, self._api)

            case _:
                raise NotImplementedError()

    async def _set_selected_target_room(self, issuer: Issuer, room_id: str):
        """
        store the room_id currently used for configuration actions.
        """
        target_room = self._api.get_room(room_id)
        if target_room:
            with target_room.acl as acl:
                if not acl.user_has_role(Role.config, user_id=issuer.user_id, user_level=issuer.power_level):
                    await self._send_notice("you're not allowed to configure this room")
                    return

            await self._api.storage.set("selected_target_room", target_room.room_id)
            await self._update_room_topic(target_room)

            self._update_cli(target_room)

        else:
            self._send_notice("room not known to the bot")

    async def _get_selected_target_room(self) -> Room | None:
        """
        acquire the currently selected target room
        """

        room_id = await self._api.storage.get("selected_target_room")

        if room_id:
            room = self._api.get_room(room_id)
            if room:
                return room
            else:
                await self._api.storage.rm("selected_target_room")

        return None

    async def _update_room_topic(self, selected_room: Room | None):
        if selected_room is not None:
            await self._api.set_room_topic(
                f"selected room: {selected_room.display_name} ({selected_room.room_id})"
            )

        else:
            # room no longer known or accessible
            await self._api.set_room_topic("no selected room")

    def _update_cli(self, target_room: Room | None = None) -> None:
        if self._cli_parser:
            if not self._api.remove_text_handler(self._cli_parser):
                raise Exception("inconsistent cli parser registration")
            self._cli_parser = None

        # TODO: if self._api.is_interaction_room(): -> we need ! prefix for commands
        self._cli_parser = CLIHandler(
            parser=self._get_parser(target_room),
            action=self._on_message,
        )

        self._api.add_text_handler(
            self._cli_parser
        )


Module = Config
