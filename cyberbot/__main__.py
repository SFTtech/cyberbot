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
DEFAULT_PLUGINPATH = "./plugins;./plugins_examples"
DEFAULT_DEVICEID = "MATRIXBOT"
DEFAULT_DBPATH = "./matrixbot.sqlite"


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

    if not 'BotMatrixId' in config \
        or not all(key in config['BotMatrixId']
                for key in ['USERNAME','PASSWORD','SERVER']):
        sys.stderr.write("""Bad config file. Please check that
config file exists and all fields are available""")
        sys.exit(-1)

    vals = config['BotMatrixId']

    username   = vals['USERNAME']
    password   = vals['PASSWORD']
    server     = vals['SERVER']
    botname    = vals.get("BOTNAME", DEFAULT_BOTNAME)
    pluginpath = [p.strip() for p in vals.get("PLUGINPATH", DEFAULT_PLUGINPATH).split(";")]
    deviceid   = vals.get("DEVICEID", DEFAULT_DEVICEID)
    store_path = vals.get("STOREPATH", "")
    dbpath     = vals.get("DBPATH", DEFAULT_DBPATH)

    environment = dict((k.upper(),v) for k,v in dict(vals).items()
                                     if k.lower() != 'password')


    async with MatrixBot(
            username,password,server,
            botname=botname,
            deviceid=deviceid,
            store_path=store_path,
            environment=environment,
            pluginpath=pluginpath,
            dbpath=dbpath
            ) as bot:
        await bot.load_rooms()
        await bot.read_plugins()
        await bot.enter_plugins_to_db()
        await bot.listen()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
    #asyncio.run(main())
