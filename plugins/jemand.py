import random
from matrix_bot_api.mregex_handler import MRegexHandler

HELP_DESC = ("(automatic)\t\tThe bot replaces 'jemand™' in a sentence with a "
             "random room member")

def register_to(bot):

    # Echo back the given command
    def jemand_callback(room, event):
        members = room.get_joined_members()
        jemand = random.choice(list(members))
        msg = event['content']['body']
        msg = msg.replace("jemand™", jemand.user_id)
        room.send_text(msg)

    # Add a command handler waiting for the echo command
    jemand_handler = MRegexHandler("jemand™", jemand_callback)
    bot.add_handler(jemand_handler)
