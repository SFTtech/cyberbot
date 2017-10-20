from matrix_bot_api.mcommand_handler import MCommandHandler

import requests


HELP_DESC = (""""!maunz                 -   miau""")

upload_url = 'https://matrix.org/_matrix/media/r0/upload'

download_url = 'https://loremflickr.com/'

def register_to(bot):    
    def maunz_callback(room, event):
        args = event['content']['body'].split()
        # remove the command
        args.pop(0)
        r = requests.get(download_url + ('/'.join(args)))

        if(r):
            img = r.content
            typ = r.headers['content-type']
            print('Downloaded', typ)
            up = room.client.api.media_upload(img, typ)
            print('Uploaded', up)
            uri = up['content_uri']
            room.send_image(uri, 'Miau')
        else:
            room.send_text('Kittens ' + download_url + ' unavailable :( ')

    maunz_handler = MCommandHandler("maunz", maunz_callback)
    bot.add_handler(maunz_handler)
