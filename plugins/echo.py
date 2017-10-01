from matrix_bot_api.mcommand_handler import MCommandHandler

HELP_DESC = ("!echo\t\t-\tEcho back the given string\n"
             "!all\t\t\t-\tHighlight all people in the channel")

def register_to(bot):

    # Echo back the given command
    def echo_callback(room, event):
        args = event['content']['body'].split()
        args.pop(0)

        room.send_text(event['sender'] + ': ' + ' '.join(args))

    # Highlight all room members
    def all_callback(room, event):
        memb = room.get_joined_members()
        room.send_text(' '.join(memb))

    # Add a command handler waiting for the echo command
    echo_handler = MCommandHandler("echo", echo_callback)
    bot.add_handler(echo_handler)

    # Add a command handler waiting for the all command
    all_handler = MCommandHandler("all", all_callback)
    bot.add_handler(all_handler)
