from __future__ import annotations

import abc
import io
import re
import shlex
from argparse import ArgumentError, ArgumentParser, Namespace, _SubParsersAction
from contextlib import redirect_stderr
from typing import Awaitable, Callable

from nio.events.room_events import RoomMessage

from ..types import Err, Ok, Result
from .types import MessageHandler, MessageText


def message_args(message: RoomMessage) -> list[str]:
    """
    get the matrix text message's content, split like a shell command.
    """
    return shlex.split(message.source["content"]["body"])


class TextHandler:
    """
    use this to process text messages in a room.
    """
    @abc.abstractmethod
    async def process(self, event: MessageText) -> None:
        pass


class RegexHandler(TextHandler):
    """
    evaluates messages against the given a regex and when it matches,
    the action function is called.
    """

    def __init__(self, regexstring: str, action: MessageHandler,
                 pre_check: Callable[[str], bool] | None = None):
        self._re = re.compile(regexstring)
        self._action = action

        self._pre_check = pre_check

    async def process(self, event: MessageText) -> None:
        if event.source["type"] == "m.room.message":
            text = event.source["content"]["body"]

            if ((self._pre_check is None or self._pre_check(text)) and self._re.match(text)):
                await self._action(event)


class CommandHandler(RegexHandler):
    """
    when a text message matches the form `!command`, the action function will be called.
    """

    def __init__(self, command: str, action: MessageHandler):
        super().__init__(rf"^!{command}(\s.*)?$", action, pre_check=lambda txt: txt.startswith('!'))


class CommandParser(ArgumentParser):
    """
    Just like argparser.ArgumentParser, but optimized for text interaction.
    It does not exit when there's parsing errors
    (ArgumentParser has exit_on_error=False for this, but it's not applied for subparsers...)
    And this parser doesn't print stuff to stderr...
    """
    def __init__(self, *args, **kwargs):
        # disable exiting and help
        # help also exits in the _HelpAction implementation...
        kwargs["exit_on_error"] = False
        super().__init__(*args, **kwargs)

    def add_subparsers(self, *args, **kwargs) -> _SubParsersAction:
        return super().add_subparsers(*args, parser_class=CommandParser, **kwargs)

    def print_usage(self, file=None):
        msg = self.format_usage()
        if file:
            file.write(msg)
        else:
            raise ArgumentError(argument=None, message=msg)

    def print_help(self, file=None):
        msg = self.format_help()
        if file:
            file.write(msg)
        else:
            # send via exception
            raise ArgumentError(argument=None, message=msg)

    def _print_message(self, message, file=None):
        """ just for _VersionAction <3... which wants to write to stdout real badly """
        raise ArgumentError(argument=None, message=message)

    def exit(self, status=0, message=None):
        raise ArgumentError(argument=None, message=message)


def argparse_room_message(cli: CommandParser, message: str) -> Result[Namespace, str]:
    """
    returns (args-Namespace, None | output-string if there was stderr output.)
    """
    args_raw = shlex.split(message)

    args = Namespace()
    output = io.StringIO()
    with redirect_stderr(output):
        try:
            args = cli.parse_args(args_raw)

        except ArgumentError as err:
            output.write(str(err))

    if output.tell():
        return Err(output.getvalue())

    return Ok(args)


class CLIHandler(TextHandler):
    """
    CLI-like input -> needs an argument parser.
    commands is a list of top level instructions, used to select this TextHandler.

    when the commands match, call the action function that gets:
    - parsed args as Namespace
    - resulting stderr of the parsing | None
    - the original message
    - the argparser used (e.g. to format help)
    """

    def __init__(self, parser: CommandParser,
                 action: Callable[[Result[Namespace, str], MessageText, CommandParser], Awaitable[None]],
                 commands: list[str] = []):
        self._parser = parser
        self._commands = commands
        self._action = action

    def _pre_check(self, txt: str) -> bool:
        if self._commands:
            space = txt.find(' ')
            if space > 0:
                return txt[:space] in self._commands
            else:
                return txt in self._commands
        else:
            return True

    async def process(self, event: MessageText):
        text = event.source["content"]["body"]

        if self._pre_check(text):
            result = argparse_room_message(self._parser, text)
            await self._action(result, event, self._parser)


class InstructionHandler(RegexHandler):
    """
    given a input string and a function, the function will be called,
    whenever `instruction...` is written at the start of the input string.
    """

    def __init__(self, instruction: str, action: MessageHandler):
        super().__init__(rf"^{instruction}(\s.*)?$", action)
