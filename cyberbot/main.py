import argparse
import asyncio
import logging
import sys

from .bot import Bot
from .config import read_config


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(stream=sys.stdout, level=level)

    logging.getLogger('peewee').setLevel(logging.INFO)
    logging.getLogger('asyncio').setLevel(logging.INFO)
    logging.getLogger('nio.responses').setLevel(logging.INFO if verbose else logging.ERROR)
    logging.getLogger('nio.crypto.log').setLevel(logging.INFO if verbose else logging.WARNING)


def cli():
    cli = argparse.ArgumentParser()
    cli.add_argument("-c", "--config", default="config.yaml",
                     help="path to the configuration file")
    cli.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    cli.add_argument("--debug-asyncio", action="store_true", help="Enable asyncio debugging")
    args = cli.parse_args()

    return args


async def run(config: str):
    config = read_config(config)

    async with Bot(config) as bot:
        await bot.run()


def main():
    args = cli()
    setup_logging(args.verbose)

    asyncio.run(run(args.config), debug=args.debug_asyncio)


if __name__ == "__main__":
    main()
