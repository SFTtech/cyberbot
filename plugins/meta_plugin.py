from matrix_bot_api.mcommand_handler import MCommandHandler
import asyncio

HELP_DESC = ("""
!listplugins\t\t\t-\tlist available plugins
!addplugin plugin [plugin2 ...]\t-\tadd plugin(s)
!remplugin plugin [plugin2 ...]\t-\tremove plugin(s)
!reload\t\t\t\t-\tReload plugins
"""[1:-1])


blacklisted = ["help" "meta"]

async def register_to(plugin):
    """
    TODO: don't add plugins twice, don't remove meta plugin etc
    """

    async def listplugins_callback(room, event):
        available = plugin.mroom.bot.available_plugins
        pluginlist = ""
        for k,v in available.items():
            indentet = "\t" + v[:-1].replace("\n", "\n\t") + v[-1]
            pluginlist += f"{k}:\n{indentet}\n"

        await plugin.send_html(f"""<pre><code>{pluginlist}</pre></code>""")
            
    listplugins_handler = MCommandHandler("listplugins", listplugins_callback)
    plugin.add_handler(listplugins_handler)


    async def addplugin_callback(room, event):
        args = event.source['content']['body'].split()
        await asyncio.gather(*(plugin.mroom.add_plugin(pname) for pname in args[1:]))
        await plugin.send_text("Call !help to see new plugins")

    addplugin_handler = MCommandHandler("addplugin", addplugin_callback)
    plugin.add_handler(addplugin_handler)


    async def remplugin_callback(room, event):
        args = plugin.extract_args(event)

        torem = list(filter(lambda x: x not in blacklisted, args[1:]))

        await asyncio.gather(*(plugin.mroom.remove_plugin(pname) for pname in torem))
        await plugin.send_text("Call !help to see new plugins")

    remplugin_handler = MCommandHandler("remplugin", remplugin_callback)
    plugin.add_handler(remplugin_handler)


    async def reload_callback(room, event):
        await plugin.room.bot.read_plugins() # look for new available plugins
        # TODO: shutdown background processes
        await plugin.send_text("Reloaded Plugins.")

    reload_handler = MCommandHandler("reload", reload_callback)
    plugin.add_handler(reload_handler)
