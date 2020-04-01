from matrix_bot_api.mcommand_handler import MCommandHandler

HELP_DESC = ("!echo\t\t\t-\tEcho back the given string\n")

def register_to(bot):

    # Echo back the given command
    async def echo_callback(room, event):
        args = event.source['content']['body'].split()
        args.pop(0)

        await room.send_text(event.source['sender'] + ': ' + ' '.join(args))

    # Add a command handler waiting for the echo command
    echo_handler = MCommandHandler("echo", echo_callback)
    bot.add_handler(echo_handler)
