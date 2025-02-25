from cyberbot.api.room_api import RoomAPI
from cyberbot.api.room_plugin import RoomPlugin
from cyberbot.api.text_handler import CommandHandler, MessageText, message_args


class Echo(RoomPlugin):
    @classmethod
    def about(cls) -> str:
        return "echo back sent text after '!echo <text>'"

    def __init__(self, api: RoomAPI):
        self._api = api

    async def init(self):
        self._api.add_text_handler(CommandHandler("echo", self._echo))

    async def _echo(self, text: MessageText) -> None:
        """
        Echo back <stuff> when somebody wrote !echo <stuff>.
        """

        args = message_args(text)[1:]

        await self._api.send_html(
            f"{self._api.format_user(text.sender)}: {' '.join(args)}"
        )


Module = Echo
