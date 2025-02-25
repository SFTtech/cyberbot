from argparse import ArgumentParser

from cyberbot.api.room_api import RoomAPI
from cyberbot.api.room_plugin import PluginConfigParser, RoomPlugin

from ..util.git_hook_handler import GitHookHandler
from .formatting import format_event


class GitLab(RoomPlugin):
    def __init__(self, api: RoomAPI):
        self._handler = GitHookHandler(
            api,
            git_variant="gitlab",
            format_event_func=format_event,
            info_url="https://docs.gitlab.com/ee/user/project/integrations/webhooks.html",
            emoji="🦊",
        )

    @classmethod
    def about(cls) -> str:
        return "GitLab notifications"

    def config_setup(self, parser: ArgumentParser) -> PluginConfigParser | None:
        return self._handler.config_setup(parser)

    async def init(self):
        await self._handler.start()


Module = GitLab
