import argparse
import configparser
import asyncio
import sys

from pathlib import Path

from matrixbot import MatrixBot

import nio

DEFAULT_BOTNAME = "Matrix Bot"
DEFAULT_PLUGINPATH = "plugins"
DEFAULT_DEVICEID = "MATRIXBOT"


# load_plugins
# plugins setup event listeners via api
# sync forever


def setup_cli():
    # Interpret command line arguments
    cli = argparse.ArgumentParser()
    cli.add_argument("-c", "--config", default="/etc/prism/config.py",
                     help="path to the configuration file")
    cli.add_argument("-m", "--mode", default="cmd",
                     help="mode of operation [\'cmd\' or \'daemon\'].")
    return cli


async def main():
    cli = setup_cli()
    args = cli.parse_args()

    # Interpret the execution mode
    exec_mode = args.mode
    # TODO: check mode

    # Read the configuration file
    config = configparser.ConfigParser()
    config.sections()
    config.read(args.config)

    if not 'BotMatrixId' in config \
        or not all(key in config['BotMatrixId']
                for key in ['USERNAME','PASSWORD','SERVER','ROOMS']):
        sys.stderr.write("""Bad config file. Please check that
        all fields are available""")
        sys.exit(-1)

    check_default = lambda attr,default_val: vals[attr] if attr in vals else default_val
    vals = config['BotMatrixId']

    username   = vals['USERNAME']
    password   = vals['PASSWORD']
    server     = vals['SERVER']
    rooms      = list(filter(lambda x: x.strip(), vals['ROOMS'].split(';')))
    botname    = check_default("BOTNAME", DEFAULT_BOTNAME)
    pluginpath = check_default("PLUGINPATH", DEFAULT_PLUGINPATH)
    deviceid   = check_default("DEVICEID", DEFAULT_DEVICEID)
    adminusers = list(filter(lambda x: x.strip(), check_default("ADMINUSERS", "").split(';')))


    async with MatrixBot(
            username,password,server,
            botname=DEFAULT_BOTNAME,
            deviceid=deviceid,
            adminusers=adminusers) as bot:
        await bot.join_rooms(rooms)
        await bot.load_plugins(pluginpath)
        await bot.listen(exec_mode)


if __name__ == "__main__":
    asyncio.run(main())
