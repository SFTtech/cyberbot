from matrix_bot_api.mcommand_handler import MCommandHandler

import requests
from random import choice


HELP_DESC = ("!pokemon\t\t-\tRetrieves the name of a pokemon by its number")

download_url = 'http://pokeapi.co/api/v2/pokemon/'

# Feel free to add
insults = ['mac using faggot', 'millenial', 'blazingly fast web developer', 'Apple Macintosh employing non-cisgender male']

def register_to(bot):
    def pokemon_callback(room, event):
        args = event['content']['body'].split()

        if(len(args) < 2):
            r = requests.get(download_url + '1')
        else:
            r = requests.get(download_url + args[1])

        if(r):
            insult = choice(insults)
            name = r.json()['name'].title()
            num = int(args[1])
            if(num > 151):
                room.send_text('There are no Pokémon above 150, but if there were, the name of № ' + args[1] + ' would be ' + name + ' you ' + insult)
            else:
                room.send_text('Pokémon № ' + args[1] + ' is ' + name)

    pokemon_handler = MCommandHandler("pokemon", pokemon_callback)
    bot.add_handler(pokemon_handler)
