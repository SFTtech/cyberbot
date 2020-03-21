import json
import requests

from matrix_bot_api.mcommand_handler import MCommandHandler

HELP_DESC = ("!corona\t\t\t-\tShow Coronavirus stats\n")

def get_stats():
    url = "https://rki-covid-api.now.sh/api/states"
    r = requests.get(url)
    j = json.loads(r.text)
    return j


def register_to(bot):

    #async def get_corona_stats()

    async def corona_callback(room, event):
        states = get_stats()['states']
        fields = states[0].keys()
        html = """<table>
    <tr>
"""
        for field in fields:
            html += f"<th>{field}</th>\n"
        html += "    </tr>\n"

        for state in states:
            html += "    <tr>\n"
            for field in fields:
                html += f"<td>{state[field]}</td>"
            html += "    </tr>\n"
        html += "</table>"
        await room.send_html(html)

    # Add a command handler waiting for the corona command
    corona_handler = MCommandHandler("corona", corona_callback)
    bot.add_handler(corona_handler)
