from random import choice
from matrix_bot_api.mregex_handler import MRegexHandler

HELP_DESC = "(automatic)\t\tThe bot responds on avowals of gratitude."

avowals = ["You're welcome!",
           "Don't mention it!",
           "My pleasure!"]

def register_to(bot):

    # Echo back the given command
    def danke_callback(room, event):
        args = event['content']['body'].split()
        args.pop(0)

        t = choice(avowals)

        room.send_text(event['sender'] + ': ' + t)

    # Add a command handler waiting for the echo command
    danke_handler = MRegexHandler(
            "(?:\W|^)"
            +"((([vV]ielen)?[dD]ank(e?))|([tT](hanks|hx))).*([bB]ernd)"
            +"(?:\W|$)", danke_callback)

    bot.add_handler(danke_handler)
