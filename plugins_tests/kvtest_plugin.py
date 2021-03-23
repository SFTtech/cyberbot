import asyncio

HELP_DESC = ("""
!addlocalval key val
!addroomval key val
!addpluginval key val
!getlocalval key
!getroomval key
!getpluginval key
!remlocalval key
!remroomval key
!rempluginval key
!getlocalkeys
!getroomkeys
!getpluginkeys
"""[1:-1])


async def register_to(plugin):

    async def addlocalval_callback(room, event):
        args = plugin.extract_args(event)
        if len(args) == 3:
            key = args[1]
            val = args[2]
            await plugin.kvstore_set_local_value(key,val)
            
    addlocalval_handler = plugin.CommandHandler("addlocalval", addlocalval_callback)
    plugin.add_handler(addlocalval_handler)

    async def addroomval_callback(room, event):
        args = plugin.extract_args(event)
        if len(args) == 3:
            key = args[1]
            val = args[2]
            await plugin.kvstore_set_room_value(key,val)
            
    addroomval_handler = plugin.CommandHandler("addroomval", addroomval_callback)
    plugin.add_handler(addroomval_handler)

    async def addpluginval_callback(room, event):
        args = plugin.extract_args(event)
        if len(args) == 3:
            key = args[1]
            val = args[2]
            await plugin.kvstore_set_plugin_value(key,val)
            
    addpluginval_handler = plugin.CommandHandler("addpluginval", addpluginval_callback)
    plugin.add_handler(addpluginval_handler)


    async def getlocalval_callback(room, event):
        args = plugin.extract_args(event)
        if len(args) == 2:
            key = args[1]
            r = await plugin.kvstore_get_local_value(key)
        await plugin.send_text(str(r));

    getlocalval_handler = plugin.CommandHandler("getlocalval", getlocalval_callback)
    plugin.add_handler(getlocalval_handler)

    async def getroomval_callback(room, event):
        args = plugin.extract_args(event)
        if len(args) == 2:
            key = args[1]
            r = await plugin.kvstore_get_room_value(key)
        await plugin.send_text(str(r));

    getroomval_handler = plugin.CommandHandler("getroomval", getroomval_callback)
    plugin.add_handler(getroomval_handler)

    async def getpluginval_callback(room, event):
        args = plugin.extract_args(event)
        if len(args) == 2:
            key = args[1]
            r = await plugin.kvstore_get_plugin_value(key)
        await plugin.send_text(str(r));

    getpluginval_handler = plugin.CommandHandler("getpluginval", getpluginval_callback)
    plugin.add_handler(getpluginval_handler)

    async def remlocalval_callback(room, event):
        args = plugin.extract_args(event)
        await plugin.kvstore_get_local_keys()
        if len(args) == 2:
            key = args[1]
            r = await plugin.kvstore_rem_local_value(key)
        await plugin.send_text(str(r));

    remlocalval_handler = plugin.CommandHandler("remlocalval", remlocalval_callback)
    plugin.add_handler(remlocalval_handler)

    async def remroomval_callback(room, event):
        args = plugin.extract_args(event)
        await plugin.kvstore_get_room_keys()
        if len(args) == 2:
            key = args[1]
            r = await plugin.kvstore_rem_room_value(key)
        await plugin.send_text(str(r));

    remroomval_handler = plugin.CommandHandler("remroomval", remroomval_callback)
    plugin.add_handler(remroomval_handler)

    async def rempluginval_callback(room, event):
        args = plugin.extract_args(event)
        await plugin.kvstore_get_plugin_keys()
        if len(args) == 2:
            key = args[1]
            r = await plugin.kvstore_rem_plugin_value(key)
        await plugin.send_text(str(r));

    rempluginval_handler = plugin.CommandHandler("rempluginval", rempluginval_callback)
    plugin.add_handler(rempluginval_handler)

    async def getlocalkeys_callback(room, event):
        r = await plugin.kvstore_get_local_keys()
        await plugin.send_text(" ".join(r));

    getlocalkeys_handler = plugin.CommandHandler("getlocalkeys", getlocalkeys_callback)
    plugin.add_handler(getlocalkeys_handler)

    async def getroomkeys_callback(room, event):
        r = await plugin.kvstore_get_room_keys()
        await plugin.send_text(" ".join(r));

    getroomkeys_handler = plugin.CommandHandler("getroomkeys", getroomkeys_callback)
    plugin.add_handler(getroomkeys_handler)

    async def getpluginkeys_callback(room, event):
        r = await plugin.kvstore_get_plugin_keys()
        await plugin.send_text(" ".join(r));

    getpluginkeys_handler = plugin.CommandHandler("getpluginkeys", getpluginkeys_callback)
    plugin.add_handler(getpluginkeys_handler)
