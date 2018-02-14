import argparse
import configparser
import importlib
import matrix_client

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
            try:
                module = loader.load_module(modname)

                # collect plugin help texts
                help_text_arr = module.HELP_DESC.split('\n') # allow multiple desc
                for h in help_text_arr:
                    help_desc.append(h)

                # Provide every module with a set of relevant environment vars
                module.DB_PATH = 'bernd.db'     # relative path to the sqlite3-dtb
                module.COUNTER_TAB = 'counters' # Name of counter table in database
                module.RATELIMIT_TAB = 'ratelimit' # Name of ratelimit table in database
                module.TRUSTED_ROOMS = rooms    # Trusted rooms to join
                module.CONFIG_USER = username   # Username, read from config file
                module.CONFIG_SERVER = server   # Server, read from config file

                # skip help module, collect all help texts before registering
                if (modname == 'plugins.help'):
                    help_module = module
                    help_modname = modname
                else:
                    module.register_to(bot)
                    print("  [+] {} loaded".format(modname))
            except ImportError as e:
                print("  [!] {} not loaded: {}".format(modname, str(e)))
    # Build the help message from the collected plugin description fragments
    help_txt = '\n'.join([
            "Bernd Lauert Commands and Capabilities",
            '-' * 80,
            '',
            ] + [ e for e in sorted(help_desc) if e != '' ])

    with open('help_text', 'w') as f:
        f.write(help_txt)

    # load the help module after all help texts have been collected
    help_module.register_to(bot)
    print("  [+] {} loaded".format(help_modname))

    # Start polling and save a handle to the child thread
    child_thread = bot.start_polling()

    print("Bernd Lauert nun.")

    """
    # Retrieve a list of joined rooms and leave all rooms, we're in alone
    cur_rooms = bot.client.get_rooms()
    for r in rooms:
        ppl = cur_rooms[r].get_joined_members()

        if (len(ppl) == 1): # we're alone in this room
            print("Detected a solitary room ({}), leaving...".format(r))
            r.leave()
    """

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
