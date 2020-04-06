from matrix_bot_api.mcommand_handler import MCommandHandler

HELP_DESC = ("!echo\t\t\t-\tEcho back the given string\n")

async def register_to(plugin):

    # Echo back the given command
    async def echo_callback(room, event):
        args = plugin.extract_args(event)
        args.pop(0)

        await plugin.send_text(event.source['sender'] + ': ' + ' '.join(args))

    # Add a command handler waiting for the echo command
    echo_handler = MCommandHandler("echo", echo_callback)
    plugin.add_handler(echo_handler)
