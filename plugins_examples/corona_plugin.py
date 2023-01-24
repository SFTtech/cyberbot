import json
import requests
import tempfile


HELP_DESC = "!corona\t\t\t-\tShow Coronavirus stats of Germany\n"

DOWNLOAD_URL = "https://api.corona-zahlen.org/map/districts-legend"

async def register_to(plugin):

    async def corona_callback(room, event):
        r = requests.get(DOWNLOAD_URL)

        if r:
            with tempfile.NamedTemporaryFile("wb", suffix=".png") as t:
                t.write(r.content)
                print(t.name)
                await plugin.send_image(t.name)
        else:
            await plugin.send_text('Corona ' + DOWNLOAD_URL + ' unavailable :( ')


    # Add a command handler waiting for the corona command
    corona_handler = plugin.CommandHandler("corona", corona_callback)
    plugin.add_handler(corona_handler)
