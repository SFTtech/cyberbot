from matrix_bot_api.mcommand_handler import MCommandHandler

import requests


HELP_DESC = (""""!pokemon                 -   pikachu""")

download_url = 'http://pokeapi.co/api/v2/pokemon/'

def register_to(bot):    
    def pokemon_callback(room, event):
        args = event['content']['body'].split()
        
        if(len(args) < 2):
            r = requests.get(download_url + '1')
        else:
            r = requests.get(download_url + args[1])

        if(r):
            room.send_text('Pokemon Nr. ' + args[1] + ' ' + r.json()['name'])

    pokemon_handler = MCommandHandler("pokemon", pokemon_callback)
    bot.add_handler(pokemon_handler)
