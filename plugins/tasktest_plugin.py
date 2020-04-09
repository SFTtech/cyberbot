from matrix_bot_api.mcommand_handler import MCommandHandler
import asyncio

HELP_DESC = ("""
!startecho text
!stopecho
""")


cur_task = None
async def register_to(plugin):


    async def startecho_callback(room, event):
        global cur_task
        args = plugin.extract_args(event)
        if cur_task is None and len(args) > 1:
            async def k():
                await plugin.send_text(args[1])
            cur_task = await plugin.start_repeating_task(k,10)
            
    startecho_handler = MCommandHandler("startecho", startecho_callback)
    plugin.add_handler(startecho_handler)


    async def stopecho_callback(room, event):
        global cur_task
        if cur_task is not None:
            await plugin.stop_task(cur_task)
            cur_task = None

    stopecho_handler = MCommandHandler("stopecho", stopecho_callback)
    plugin.add_handler(stopecho_handler)
