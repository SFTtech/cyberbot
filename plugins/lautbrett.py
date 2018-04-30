from matrix_bot_api.mcommand_handler import MCommandHandler
import requests

HELP_DESC = ("!laut\t\t\t-\tPlay something on the lautbrett")


def register_to(bot):

    # Echo back the given command
    def laut_callback(room, event, data):
        args = event['content']['body'].split()
        args.pop(0)
        sound_id = args[0]

        r = requests.get('https://bot.stusta.de/set/{}'
                         .format(sound_id)
        )

#        room.send_text("das lautbrett spielt {} ..., danke {}".format(sound_id, event['sender']))

    # Add a command handler waiting for the echo command
    laut_handler = MCommandHandler("laut", laut_callback)
    bot.add_handler(laut_handler)
