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
DEFAULT_PLUGINPATH = "./plugins"
DEFAULT_DEVICEID = "MATRIXBOT"
DEFAULT_DBPATH = "./matrixbot.sqlite"
DEFAULT_BIND_ADDRESS = "localhost"
DEFAULT_BIND_PORT = "8080"

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

    username     = vals['USERNAME']
    password     = vals['PASSWORD']
    server       = vals['SERVER']
    botname      = vals.get("BOTNAME", DEFAULT_BOTNAME)
    pluginpath   = [p.strip() for p in vals.get("PLUGINPATH", DEFAULT_PLUGINPATH).split(";")]
    deviceid     = vals.get("DEVICEID", DEFAULT_DEVICEID)
    store_path   = vals.get("STOREPATH", "")
    dbpath       = vals.get("DBPATH", DEFAULT_DBPATH)

    environment = dict((k.upper(),v) for k,v in dict(vals).items()
                                     if k.lower() != 'password')
    global_pluginpath = vals.get("GLOBAL_PLUGINPATH", "")
    global_plugins = [p.strip() for p in vals.get("GLOBAL_PLUGINS", "").split(";")]


    async with MatrixBot(
            username,password,server,
            botname=botname,
            deviceid=deviceid,
            store_path=store_path,
            environment=environment,
            pluginpath=pluginpath,
            global_pluginpath=global_pluginpath,
            dbpath=dbpath,
            global_plugins=global_plugins,
            ) as bot:
        await bot.start()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
    #asyncio.run(main())
