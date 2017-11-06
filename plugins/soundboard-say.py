from matrix_bot_api.mcommand_handler import MCommandHandler
import requests
import re

HELP_DESC = ("!say\t\t\t\t\t\t-\tMake the soundboard say something")

def register_to(bot):
    def say_callback(room, event):
        args = event['content']['body'].split()[1:]

        # prefix the phrase with [de] or [en] to use the
        # right voice. see /usr/share/espeak-data/voices for all options
        match = re.match(r"\[(.*)\]", args[0])
        if match:
            voice = match.groups(1)[0]
            args = args[1:]
        else:
            voice = 'de'

        payload = (('phrase',' '.join(args)), ('voice',voice))
        r = requests.post('https://bot.stusta.de/speak', data=payload)
    echo_handler = MCommandHandler("say", say_callback)
    bot.add_handler(echo_handler)

