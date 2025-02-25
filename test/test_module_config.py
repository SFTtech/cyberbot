import re
from argparse import ArgumentError

import pytest

from cyberbot.modules.config import Config


def test_config():
    """
    ArgumentParser _HelpAction wants to exit the program real badly.
    we hacked it in our CommandParser variant so it doesn't exit, but still prints the help.
    """
    mod = Config(api=None)
    cli = mod._get_parser()

    with pytest.raises(ArgumentError) as err:
        cli.parse_args(["room", "--help"])

    assert re.match(r"^usage:\s+\<config\>\s+room", err.value.message)
