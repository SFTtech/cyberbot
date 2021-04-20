import argparse
import configparser
import asyncio
import sys
import logging

from pathlib import Path
from pprint import pprint

from matrixbot import MatrixBot

import nio


# load_plugins
# plugins setup event listeners via api
# sync forever

def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(stream=sys.stdout, level=level)


def setup_cli():
    # Interpret command line arguments
    cli = argparse.ArgumentParser()
    cli.add_argument("-c", "--config",
                     help="path to the configuration file")
    cli.add_argument("-v", action="store_true", help="Enable verbose output")
    return cli


async def main():

    cli = setup_cli()
    args = cli.parse_args()
    setup_logging(args.v)

    # Read the configuration file
    config = configparser.ConfigParser()
    config.sections()
    config.read(args.config)

    async with MatrixBot(config) as bot:
        await bot.start()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
    #asyncio.run(main())
