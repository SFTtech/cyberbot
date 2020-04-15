**Bernd Lauert**
----------------

Plugins are python files which are located in the `plugins` folder.
They must end in `.py` to be recognized by the bot.
Each plugin must contain a global `HELP_DESC` variable with a short string
explaining the plugin.

Furthermore, an asyncio function `register_to(plugin)` has to be defined.

The `plugin` argument exposes a lot of functionality via helper-functions, e.g.:
	- Handler Constructors
	- room interaction (`send_text`, `send_image`, ...)
	- a persistent key-value store
	- functions for creating asyncio task

For more information look into the file bernd/plugin.py.

As the bot heavily uses python's `asyncio`, most functions create coroutines which
must be awaited.

Example:
```python
HELP_DESC = ("!echo\t\t\t-\tEcho back the given string\n")

async def register_to(plugin):

    # Echo back the given command
    async def echo_callback(room, event):
        args = plugin.extract_args(event)
        args.pop(0)

        await plugin.send_text(event.source['sender'] + ': ' + ' '.join(args))

    # Add a command handler waiting for the echo command
    echo_handler = plugin.CommandHandler("echo", echo_callback)
    plugin.add_handler(echo_handler)
```
