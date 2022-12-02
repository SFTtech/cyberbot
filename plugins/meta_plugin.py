import asyncio

HELP_DESC = """
!listplugins\t\t-\tlist addable plugins
!addplugin plugin [...]\t-\tadd plugin(s) (--all for all)
!remplugin plugin [...]\t-\tremove plugin(s)
"""


blacklisted = ["help" "meta"]


async def register_to(plugin):
    """
    TODO: don't add plugins twice, don't remove meta plugin etc
    """

    async def listplugins_callback(room, event):
        available = plugin.mroom.bot.available_plugins
        pluginlist = ""
        for k, v in available.items():
            indentet = "\t" + v[:-1].replace("\n", "\n\t") + v[-1]
            pluginlist += f"{k}:\n{indentet}\n"

        await plugin.send_html(f"""<pre><code>{pluginlist}</pre></code>""")

    listplugins_handler = plugin.CommandHandler("listplugins", listplugins_callback)
    plugin.add_handler(listplugins_handler)

    async def addplugin_callback(room, event):
        curr_plugins = [p.pluginname for p in plugin.mroom.plugins]
        args = event.source["content"]["body"].split()
        if len(args) > 1 and args[1] == "--all":
            await asyncio.gather(
                *(
                    plugin.mroom.add_plugin(pname)
                    for pname in plugin.mroom.bot.available_plugins
                    if pname not in curr_plugins
                )
            )
        else:
            await asyncio.gather(
                *(
                    plugin.mroom.add_plugin(pname)
                    for pname in args[1:]
                    if pname not in curr_plugins
                )
            )

        await plugin.send_text("Call !help to see new plugins")

    addplugin_handler = plugin.CommandHandler("addplugin", addplugin_callback)
    plugin.add_handler(addplugin_handler)

    async def remplugin_callback(room, event):
        args = plugin.extract_args(event)

        torem = list(filter(lambda x: x not in blacklisted, args[1:]))

        await asyncio.gather(*(plugin.mroom.remove_plugin(pname) for pname in torem))
        await plugin.send_text("Call !help to see new plugins")

    remplugin_handler = plugin.CommandHandler("remplugin", remplugin_callback)
    plugin.add_handler(remplugin_handler)


#    async def reload_callback(room, event):
#        # if some plugins are still in the register_to funciton, they will not
#        # be stopped :(
#        await plugin.mroom.bot.read_plugins() # look for new available plugins
#        await asyncio.gather(*(p.stop_all_tasks() for p in plugin.mroom.plugins)) # stop running tasks
#        await plugin.mroom.load_plugins()
#        # await plugin.send_text("Reloaded Plugins.")
#
#    reload_handler = plugin.CommandHandler("reload", reload_callback)
#    plugin.add_handler(reload_handler)
