import argparse
import configparser
import asyncio
import sys
import logging

from pathlib import Path
from pprint import pprint

from matrixbot import MatrixBot

import nio

DEFAULT_BOTNAME = "Matrix Bot"
DEFAULT_PLUGINPATH = "plugins"
DEFAULT_DEVICEID = "MATRIXBOT"


# load_plugins
# plugins setup event listeners via api
# sync forever

def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(stream=sys.stdout, level=level)


def setup_cli():
    # Interpret command line arguments
    cli = argparse.ArgumentParser()
    cli.add_argument("-c", "--config", default="/etc/prism/config.py",
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

    if not 'BotMatrixId' in config \
        or not all(key in config['BotMatrixId']
                for key in ['USERNAME','PASSWORD','SERVER']):
        sys.stderr.write("""Bad config file. Please check that
config file exists and all fields are available""")
        sys.exit(-1)

    check_default = lambda attr,default_val: vals[attr] if attr in vals else default_val
    vals = config['BotMatrixId']

    username   = vals['USERNAME']
    password   = vals['PASSWORD']
    server     = vals['SERVER']
    botname    = check_default("BOTNAME", DEFAULT_BOTNAME)
    pluginpath = check_default("PLUGINPATH", DEFAULT_PLUGINPATH)
    deviceid   = check_default("DEVICEID", DEFAULT_DEVICEID)
    store_path = check_default("STOREPATH", "")

    environment = dict((k.upper(),v) for k,v in dict(vals).items()
                                     if k.lower() != 'password')


    async with MatrixBot(
            username,password,server,
            botname=botname,
            deviceid=deviceid,
            store_path=store_path,
            environment=environment,
            plugindir=pluginpath
            ) as bot:
        await bot.load_rooms()
        await bot.read_plugins()
        await bot.listen()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
    #asyncio.run(main())
