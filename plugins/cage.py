from matrix_bot_api.mcommand_handler import MCommandHandler

import requests
import datetime
import sqlite3


HELP_DESC = ("!cage\t\t\t\t\t\t-\tDisplays an image of the greatest actor of all times.")

upload_url = 'https://matrix.org/_matrix/media/r0/upload'

download_url = 'https://www.placecage.com/'

def register_to(bot):    
    def cage_callback(room, event):

        # rate limiting
        date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("select last from {}".format(RATELIMIT_TAB)
                  + " where name = 'cage'")
        lastdate = c.fetchall()[0][0]
        
        ### todo(stefan.huber@stusta.de):
        if (date-lastdate) > 60mim:
            c.execute("update {}".format(COUNTER_TAB)
                  + " set counter=counter+1 where name = 'industrie'")

        
        conn.close()


        # actual cage code
        args = event['content']['body'].split()
        # remove the command
        args.pop(0)

        if(len(args) < 2):
            r = requests.get(download_url + '300/200')
        else:
            r = requests.get(download_url + ('/'.join(args)))

        if(r):
            img = r.content
            typ = r.headers['content-type']
            print('[i] Downloaded', typ)
            up = room.client.api.media_upload(img, typ)
            print('[i] Uploaded', up)
            uri = up['content_uri']
            room.send_image(uri, 'Hübschlon')
        else:
            room.send_text('Cage ' + download_url + ' unavailable :( ')

    conn = sqlite.connect(DB_PATH)
    c = conn.cursor()

    try:
        # look if there is an entry for this plugin
        c.execute("select name from {}".format(RATELIMIT_TAB)
                  + " where name = 'cage'")

        # if not, create one
        if (c.fetchall() == []):
            c.execute("insert into {}".format(RATELIMIT_TAB)
                      + " values ('cage', '2001-01-01 00:00:00.000')")

    except sqlite3.OperationalError as e:
        # if the table does not exist
        if (e.args[0].find('no such table') != -1):
            # create it
            c.execute("create table {}".format(RATELIMIT_TAB)
                      + " (name text, last text)")

            # and add an entry for this plugin
            c.execute("insert into {}".format(RATELIMIT_TAB)
                      + " values ('cage', '2001-01-01 00:00:00.000')")
        else:
            print("Encountered miscellaneous sqlite error:", e)

    conn.commit()
    conn.close()

    cage_handler = MCommandHandler("cage", cage_callback)
    bot.add_handler(cage_handler)