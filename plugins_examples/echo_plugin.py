HELP_DESC = "!echo\t\t\t-\tEcho back the given string\n"


async def register_to(plugin):

    # Echo back the given command
    async def echo_callback(room, event):
        args = plugin.extract_args(event)
        args.pop(0)

        await plugin.send_html(
            await plugin.format_user_highlight(event.sender) + ": " + " ".join(args)
        )

    # Add a command handler waiting for the echo command
    echo_handler = plugin.CommandHandler("echo", echo_callback)
    plugin.add_handler(echo_handler)
