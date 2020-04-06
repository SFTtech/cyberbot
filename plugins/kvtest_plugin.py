from matrix_bot_api.mcommand_handler import MCommandHandler
import asyncio

HELP_DESC = ("""
!addval key val
!getval key
!remval key
!getkeys
"""[1:-1])


async def register_to(plugin):

    async def addval_callback(room, event):
        args = plugin.extract_args(event)
        if len(args) == 3:
            key = args[1]
            val = args[2]
            await plugin.kvstore_set_value(key,val)
            
    addval_handler = MCommandHandler("addval", addval_callback)
    plugin.add_handler(addval_handler)


    async def getval_callback(room, event):
        args = plugin.extract_args(event)
        if len(args) == 2:
            key = args[1]
            r = await plugin.kvstore_get_value(key)
        await plugin.send_text(str(r));

    getval_handler = MCommandHandler("getval", getval_callback)
    plugin.add_handler(getval_handler)


    async def remval_callback(room, event):
        args = plugin.extract_args(event)
        plugin.kvstore_get_keys()
        if len(args) == 2:
            key = args[1]
            r = await plugin.kvstore_rem_value(key)
        await plugin.send_text(str(r));

    remval_handler = MCommandHandler("remval", remval_callback)
    plugin.add_handler(remval_handler)


    async def getkeys_callback(room, event):
        r = await plugin.kvstore_get_keys()
        await plugin.send_text(" ".join(r));

    getkeys_handler = MCommandHandler("getkeys", getkeys_callback)
    plugin.add_handler(getkeys_handler)
