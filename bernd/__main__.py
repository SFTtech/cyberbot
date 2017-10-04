import argparse
import configparser
import importlib

# In order to provide the 'daemon' execution mode, matrix_bot_api and
# matrix_client modules are modified to return a thread object from the
# start_polling function. This import therefore needs to respect this
# dependency (e.g. symlinks to the modified repos in the current folder).
# If the module APIs are enhanced in the future, this can be
# ignored.
from matrix_bot_api.matrix_bot_api import MatrixBotAPI
from pathlib import Path

def main():

    # Interpret command line arguments
    cmd = argparse.ArgumentParser()
    cmd.add_argument("-c", "--config", default="/etc/prism/config.py",
                     help="path to the configuration file")
    cmd.add_argument("-m", "--mode", default="cmd",
                     help="mode of operation [\'cmd\' or \'daemon\'].")
    args = cmd.parse_args()

    # Interpret the execution mode
    exec_mode = args.mode

    # Read the configuration file
    config = configparser.ConfigParser()
    config.sections()
    config.read(args.config)


    username = config['BotMatrixId']['USERNAME']
    password = config['BotMatrixId']['PASSWORD']
    server = config['BotMatrixId']['SERVER']
    rooms = config['BotMatrixId']['ROOMS'].split(';')

    print("Bernd steht langsam auf...")

    # Create an instance of the MatrixBotAPI

    # The room argument can be provided with empty list or None, as the original
    # bot API doesn't support string arguments but only room objects, which we
    # can't create without an existing bot object. Trusted rooms from the config
    # file can be joined later.

    # Providing empty list also prevents the bot from accepting incoming room
    # invites. Providing None causes the bot to accept invites. In this case,
    # a plugin developer may choose to restrict the plugin capabilities to the
    # trusted rooms, defined in the config.
    bot = MatrixBotAPI(username, password, server, None)

    # With an established connection and existing bot object, we tell the bot
    # manually to join or specified rooms
    for roomid in rooms:
        print("Trying to join room {}".format(roomid))
        try:
            bot.handle_invite(roomid, None)
        except matrix_client.errors.MatrixRequestError:
            print("Failed to join room {}".format(roomid))

    # Import all defined plugins
    plugin_path = Path(__file__).resolve().parent.parent / "plugins"
    print("Loading plugins from: {}".format(plugin_path))

    help_desc = []

    for filename in plugin_path.glob("*.py"):
        if (plugin_path / filename).exists():

            modname = 'plugins.%s' % filename.stem
            loader = importlib.machinery.SourceFileLoader(
                modname, str(filename))

            module = loader.load_module(modname)
            help_desc.append(module.HELP_DESC)  # collect plugin help texts

            # Provide every module with a set of relevant environment vars
            module.TRUSTED_ROOMS = rooms    # Trusted rooms to join

            # skip help module, collect all help texts before registering
            if (modname == 'plugins.help'):
                help_module = module
                help_modname = modname
            else:
                module.register_to(bot)
                print("  [+] {} loaded".format(modname))

    # Build the help message from the collected plugin description fragments
    help_desc.sort(reverse=True)

    line = ''
    for i in range(80):
        line += '-'
    help_desc.insert(0, line)

    help_desc.insert(0, '\nBernd Lauert Commands and Capabilities')
    help_txt = "\n".join(help_desc)

    with open('help_text', 'w') as f:
        f.write(help_txt)

    # load the help module after all help texts have been collected
    help_module.register_to(bot)
    print("  [+] {} loaded".format(help_modname))

    # Start polling and save a handle to the child thread
    child_thread = bot.start_polling()

    print("Bernd Lauert nun.")

    if (exec_mode == "cmd"):
        # Infinitely read stdin to stall main thread
        while True:
            try:
                w = input("press q+<enter> or ctrl+d to quit\n")
                if (w == 'q'):
                    return 0
            except EOFError:
                return 0

    elif (exec_mode == "daemon"):
        # Wait on the child worker thread to exit
        print("Executing in daemon mode. Suspending main thread...")
        child_thread.join()
        print("Child worker thread died. Exiting...")
        return 0
    else:
        print("Unknown operation mode given. Exiting...")
        return -1

if __name__ == "__main__":
    main()
