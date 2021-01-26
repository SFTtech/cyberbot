#!/usr/bin/env python3

HELP_DESC = ("(automatic)\t\t\t-\tEcho a sent request\n")

async def register_to(plugin):
    async def echo(request):
        await plugin.send_text(await request.text())

    path = "room-" + plugin.mroom.room_id
    res = await plugin.http_register_path(path, echo) 
