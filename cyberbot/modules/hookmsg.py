from __future__ import annotations

import json
import random
import string
import textwrap
import typing
from argparse import ArgumentParser, Namespace

from pydantic import BaseModel

from cyberbot.api.room_api import RoomAPI
from cyberbot.api.room_plugin import PluginConfigParser, RoomPlugin
from cyberbot.service.http_server import HTTPServer, Request, Response, ResponseStream


class _WebHook(BaseModel):
    subpath: str
    description: str


# TODO: this is pretty duplicated with util.GitHookHandler -> unify!
class HookMsg(RoomPlugin):
    def __init__(self, api: RoomAPI):
        self._api = api

        self._http_server: HTTPServer = typing.cast(
            HTTPServer,
            self._api.get_service("http_server")
        )

        self._webhooks: dict[str, _WebHook] = dict()
        self._store_key_hooks = "hooks"

        self._http_subpath = "hookmsg"

    @classmethod
    def about(cls) -> str:
        return "Message to room via http link"

    def config_setup(self, parser: ArgumentParser) -> PluginConfigParser | None:
        sp = parser.add_subparsers(dest="hookmsg_action", required=True)

        sp.add_parser("help", help="what does this plugin even do?")

        # hook
        hook_p = sp.add_parser("hook", help="manage message webhook URLs")
        hook_sp = hook_p.add_subparsers(dest="hook_action", required=True)

        hook_new_p = hook_sp.add_parser("new", help="create a new message webhook URL")
        hook_new_p.add_argument("description", help="what's this hook for?")

        hook_sp.add_parser("list", help="show which hooks are currently active")

        hook_rm_p = hook_sp.add_parser("rm", help="delete a message hook")
        hook_rm_p.add_argument("id", help="id of the hook to remove")

        return self._parse_config

    async def _parse_config(self, args: Namespace, config_api: RoomAPI) -> None:
        match args.hookmsg_action:
            case "help":
                await self._help(config_api)
            case "hook":
                match args.hook_action:
                    case "new":
                        await self._cfg_hook_new(config_api, args.description)
                    case "list":
                        await self._cfg_hook_list(config_api)
                    case "rm":
                        await self._cfg_hook_rm(config_api, args.id)

                    case _:
                        raise NotImplementedError()

            case _:
                raise NotImplementedError()

    async def _help(self, config_api: RoomAPI):
        help_text = textwrap.dedent("""\
        Available subcommands:
            hook list               - show active webhooks
            hook new                - generate url and secrettoken for a new webhook
            hook rm                 - remove a webhook

        How does it work?
            Send messages from anywhere to the secret hook url - it will show up in the chatroom.

        Examples:
        curl -F text="some message" <webhook url>
        curl -X POST -H "Content-Type: application/json" --data '{"notice": true, "html": "<code>rofl</code>"}' <url>
        curl -X POST -H "Content-Type: application/json" --data '{"notice": false, "text": "best message"}' <url>
        curl -X POST -H "Content-Type: text/plain" --data 'wow so plain' <url>

        """)

        await config_api.send_html(config_api.format_code(help_text))

    async def _cfg_hook_list(self, config_api: RoomAPI) -> None:
        lines = [
            f"- {'id':>16} - description"
        ]
        for _, hook in sorted(self._webhooks.items()):
            lines.append(f"- {hook.subpath} - {hook.description}")

        await config_api.send_html(config_api.format_code("\n".join(lines)))

    async def _cfg_hook_new(self, config_api: RoomAPI, description: str) -> None:
        if not self._http_server:
            raise Exception("http server not known")

        chars = string.ascii_letters + string.digits
        subpath = "".join(random.choices(chars, k=16))

        hook = _WebHook(subpath=subpath, description=description)
        await self._add_hook(hook)
        await self._store_hooks()

        url = await self._format_url(subpath)

        await config_api.send_text("WebHook created successfully:")
        await config_api.send_html(config_api.format_code(f"Payload URL: {url}"))

    async def _add_hook(self, hook: _WebHook) -> None:
        path = self._get_subpath(hook.subpath)
        await self._http_server.register_path(path, self._handle_hook)
        self._webhooks[hook.subpath] = hook

    async def _store_hooks(self) -> None:
        hook_data = json.dumps([hook.model_dump() for hook in self._webhooks.values()])
        await self._api.storage.set(self._store_key_hooks, hook_data)

    async def _cfg_hook_rm(self, config_api: RoomAPI, hook_id: str) -> None:
        hook = self._webhooks.pop(hook_id, None)
        if hook is None:
            config_api.send_notice("hook with this id not known")
            return

        try:
            path = self._get_subpath(hook.subpath)
            await self._http_server.deregister_path(path)
            await self._store_hooks()
            await config_api.send_notice("hook removed.")
        except Exception:
            await config_api.send_notice("exception during removal - see log.")
            raise

    def _get_subpath(self, subpath: str) -> str:
        return f"{self._http_subpath}/{subpath}"

    async def _format_url(self, subpath: str) -> str:
        return await self._http_server.format_url(self._get_subpath(subpath))

    async def init(self):
        await self._load_webhooks()

    async def _load_webhooks(self):
        """
        restore available hooks from storage.
        """
        if hooks_raw := await self._api.storage.get(self._store_key_hooks):
            for hook_raw in json.loads(hooks_raw):
                hook = _WebHook(**hook_raw)
                await self._add_hook(hook)

    async def _handle_hook(self, path: str, request: Request) -> ResponseStream | None:
        """
        called by GitHookServer when we received a hook from a git hosing service.
        """

        text: str | None = None
        notice = False
        html = False

        match request.content_type:
            case "text/plain":
                text = await request.text()

            case "application/json" | "multipart/form-data":
                match request.content_type:
                    case "application/json":
                        payload = await request.json()
                    case "multipart/form-data":
                        payload = await request.post()
                    case _:
                        raise RuntimeError("unreachable")

                if notice_raw := payload.get("notice"):
                    notice = True if notice_raw is True or notice_raw.lower() == "true" else False

                if html_raw := payload.get("html"):
                    text = html_raw
                    html = True

                if text_raw := payload.get("text"):
                    text = text_raw
                    html = True

            case _:
                return Response(status=400, text=f"unknown content type {request.content_type}")

        if text:
            if html:
                await self._api.send_html(text, notice=notice)
            else:
                await self._api.send_text(text, notice=notice)

            return Response(status=200, text="OK")

        return Response(status=200, text="no content")


Module = HookMsg
