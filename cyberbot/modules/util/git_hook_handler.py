from __future__ import annotations

import json
import random
import string
import textwrap
import typing
from argparse import ArgumentParser, Namespace

from pydantic import BaseModel

from cyberbot.api.room_api import RoomAPI
from cyberbot.service.base.git_hook_server import BaseGitHookHandler, GitHookServer

from .git_formatter import GitFormatter

if typing.TYPE_CHECKING:
    from typing import Any

    from ...api.room_plugin import PluginConfigParser


class _WebHook(BaseModel):
    subpath: str
    secret: str
    description: str


# TODO: this is pretty duplicated with hookmsg.HookMsg -> unify!
class GitHookHandler(BaseGitHookHandler):
    """
    A HookManager loads and stores secrettokens and registers them to the
    global GitHookServer.
    Can be used to register different plugins, e.g. the gitlab or the github plugin
    One only needs to provide which endpoint to use and how to format the received events
    """

    def __init__(
        self,
        api: RoomAPI,
        git_variant: str,
        formatter: GitFormatter,
        info_url: str,
        new_hook_message: str = "",
    ):
        """
        git: the git endpoint to use, e.g. gitlab or github
        """
        self._api = api
        # {url_subpath: web-hook}
        self._webhooks: dict[str, _WebHook] = dict()

        self._git_hook_server: GitHookServer = typing.cast(
            GitHookServer,
            self._api.get_service(f"{git_variant}_hook_server")
        )
        self._git_variant = git_variant
        self._store_key_hook = f"{self._git_variant}_hooks"

        self._formatter: GitFormatter = formatter
        self._info_url = info_url
        self._new_hook_message = new_hook_message

    def config_setup(self, parser: ArgumentParser) -> PluginConfigParser | None:
        sp = parser.add_subparsers(dest=f"{self._git_variant}_action", required=True)

        sp.add_parser("help", help="what does this plugin even do?")

        # hook
        hook_p = sp.add_parser("hook", help=f"manage {self._git_variant} WebHook URLs")
        hook_sp = hook_p.add_subparsers(dest=f"{self._git_variant}_hook_action", required=True)

        hook_new_p = hook_sp.add_parser("new", help=f"create a new {self._git_variant} WebHook URL")
        hook_new_p.add_argument("description", help="what's this hook for?")

        hook_sp.add_parser("list", help="show which hooks are currently active")

        hook_rm_p = hook_sp.add_parser("rm", help="delete a hook")
        hook_rm_p.add_argument("id", help="id of the hook to remove")

        # config
        config_p = sp.add_parser("config", help="control the look and feel")
        config_sp = config_p.add_subparsers(dest=f"{self._git_variant}_config_action", required=True)

        config_sp.add_parser("show")
        config_set_p = config_sp.add_parser("set")
        config_set_p.add_argument("key")
        config_set_p.add_argument("value")

        return self._parse_config

    async def _parse_config(self, args: Namespace, config_api: RoomAPI) -> None:
        match getattr(args, f"{self._git_variant}_action"):
            case "help":
                await self._help(config_api)
            case "hook":
                match getattr(args, f"{self._git_variant}_hook_action"):
                    case "new":
                        await self._cfg_hook_new(config_api, args.description)
                    case "list":
                        await self._cfg_hook_list(config_api)
                    case "rm":
                        await self._cfg_hook_rm(config_api, args.id)

                    case _:
                        raise NotImplementedError()

            case "config":
                match getattr(args, f"{self._git_variant}_config_action"):
                    case "show":
                        await self._cfg_config_show(config_api)
                    case "set":
                        await self._cfg_config_set(config_api, args.key, args.value)

                    case _:
                        raise NotImplementedError()

            case _:
                raise NotImplementedError()

    async def _cfg_hook_new(self, config_api: RoomAPI, description: str) -> None:
        chars = string.ascii_letters + string.digits
        subpath = "".join(random.choices(chars, k=16))
        secret = "".join(random.choices(chars, k=20))

        hook = _WebHook(subpath=subpath, secret=secret, description=description)
        self._add_hook(hook)
        await self._store_hooks()

        url = await self._git_hook_server.format_url(subpath)

        await config_api.send_text("WebHook created successfully:")
        html = f"Payload URL: {url}\nSecret: {secret}\n{self._new_hook_message}"
        await config_api.send_html(config_api.format_code(html))

    def _add_hook(self, hook: _WebHook) -> None:
        self._git_hook_server.register_hook(hook.subpath, hook.secret, self)
        self._webhooks[hook.subpath] = hook

    async def _cfg_hook_list(self, config_api: RoomAPI) -> None:
        lines = [
            f"- {'id':>16} - description"
        ]
        for _, hook in sorted(self._webhooks.items()):
            lines.append(f"- {hook.subpath} - {hook.description}")

        await config_api.send_html(config_api.format_code("\n".join(lines)))

    async def init(self) -> None:
        await self._load_webhooks()

    async def _load_webhooks(self):
        """
        restore available tokens from storage.
        """
        if hooks_raw := await self._api.storage.get(self._store_key_hook):
            for hook_raw in json.loads(hooks_raw):
                hook = _WebHook(**hook_raw)
                self._add_hook(hook)

    async def _store_hooks(self) -> None:
        hook_data = json.dumps([hook.model_dump() for hook in self._webhooks.values()])
        await self._api.storage.set(self._store_key_hook, hook_data)

    async def _cfg_hook_rm(self, config_api: RoomAPI, hook_id: str) -> None:
        hook = self._webhooks.pop(hook_id, None)
        if hook is None:
            config_api.send_notice("hook with this id not known")
            return

        try:
            await self._git_hook_server.deregister_hook(hook.subpath)
            await self._store_hooks()
            await config_api.send_notice("hook removed.")
        except Exception:
            await config_api.send_notice("exception during removal - see log.")
            raise

    async def _help(self, config_api: RoomAPI):
        help_text = textwrap.dedent(f"""\
        room config {self._git_variant} <subcommand> [options...]
        Available subcommands:
            hook list               - show active webhooks
            hook new                - generate url and secrettoken for a new webhook
            hook rm                 - remove a webhook
            config                  - change the way that notifications are printed

        How does it work?
            You first create a new secret token for a hook using the 'newhook' command.
            Then open your {self._git_variant} repo (or group) page and navigate to 'Settings>Webhooks'.
            There, you enter the url and secret token returned by the 'newtoken'
            command and enter all event types you want to get notifications for and
            press 'Add webhook'.

        See "{self._info_url}" for more information on {self._git_variant} webhooks.
        """)

        await config_api.send_html(config_api.format_code(help_text))

    async def _cfg_config_show(self, config_api: RoomAPI) -> None:
        config = await self._get_config()
        await config_api.send_html(
            config_api.format_code(
                "\n".join(f"{k}:\t{v}" for k, v in config.items())
            )
        )

    async def _cfg_config_set(self, config_api: RoomAPI, key: str, value: str):
        config = await self._get_config()
        if key not in config:
            await self._api.send_text(f"unknown config key {key!r}")
            return

        config[key] = value.lower() == "true"
        await self._api.storage.set("config", json.dumps(config))
        await self._api.send_text(f"set {key!r} to {config[key]}")

    async def _get_config(self) -> dict[str, bool]:
        custom_config_raw = (await self._api.storage.get("config")) or "{}"
        custom_config = json.loads(custom_config_raw)

        config = self._formatter.get_config() | custom_config
        return config

    async def handle_git_hook(self, subpath: str, event: str, content: Any) -> None:
        """
        called by GitHookServer when we received a hook from a git hosing service.
        """
        self._api.log.info(f"Token event received: {event}")

        config = await self._get_config()
        text = self._formatter.format(
            event,
            content,
            config,
        )
        if text is not None:
            await self._api.send_html(text, notice=config["notice"])
