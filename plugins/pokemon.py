from matrix_bot_api.mcommand_handler import MCommandHandler

import requests


HELP_DESC = ("!pokemon\t\t\t\t\t-\tRetrieves the name of a pokemon by number. Eg. !pokemon 4 yields Glumanda.\n")

download_url = 'http://pokeapi.co/api/v2/pokemon/'

def register_to(bot):    
    def pokemon_callback(room, event):
        args = event['content']['body'].split()
        
        if(len(args) < 2):
            r = requests.get(download_url + '1')
        else:
            r = requests.get(download_url + args[1])

        if(r):
            name = r.json()['name'].title()
            num = int(args[1])
            if(num > 151):
                room.send_text('There are no pokemon above 150, but if there were, its name would be ' + name + ' you mac using faggot.')
            else:
                room.send_text('Pokemon Nr. ' + args[1] + ' ' + name)

    pokemon_handler = MCommandHandler("pokemon", pokemon_callback)
    bot.add_handler(pokemon_handler)
