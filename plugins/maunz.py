from matrix_bot_api.mcommand_handler import MCommandHandler

import requests
import datetime
import sqlite3

maunz_ratelimit = 900 # 60 seconds * 15 minutes


HELP_DESC = ("!maunz\t\t\t\t\t\t-\tDisplays cute kittens from loremflickr")

upload_url = 'https://matrix.org/_matrix/media/r0/upload'

download_url = 'https://loremflickr.com/'

def register_to(bot):
    def maunz_callback(room, event):
        
        # rate limiting
        formatstring = '%Y-%m-%d %H:%M:%S.%f'
        now = datetime.datetime.now()
        nowstr = now.strftime(formatstring)[:-3]
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("select last from {}".format(RATELIMIT_TAB)
                  + " where name = 'maunz'")
        laststr = c.fetchall()[0][0]
        last = laststr.strftime(formatstring)
        diff = now - last
        diff = diff.seconds

        if diff < cage_ratelimit:
            room.send_text('Last Maunz was not long ago, so... no!')
            conn.close()
            return

        c.execute("update {}".format(RATELIMIT_TAB)
                  + " set last={} where name = 'maunz'".format(date))
        conn.commit()
        conn.close()

        # actual maunz code

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
            room.send_image(uri, 'Miau')
        else:
            room.send_text('Kittens ' + download_url + ' unavailable :( ')

    conn = sqlite.connect(DB_PATH)
    c = conn.cursor()

    try:
        # look if there is an entry for this plugin
        c.execute("select name from {}".format(RATELIMIT_TAB)
                  + " where name = 'maunz'")

        # if not, create one
        if (c.fetchall() == []):
            c.execute("insert into {}".format(RATELIMIT_TAB)
                      + " values ('maunz', '2001-01-01 00:00:00.000')")

    except sqlite3.OperationalError as e:
        # if the table does not exist
        if (e.args[0].find('no such table') != -1):
            # create it
            c.execute("create table {}".format(RATELIMIT_TAB)
                      + " (name text, last text)")

            # and add an entry for this plugin
            c.execute("insert into {}".format(RATELIMIT_TAB)
                      + " values ('maunz', '2001-01-01 00:00:00.000')")
        else:
            print("Encountered miscellaneous sqlite error:", e)

    conn.commit()
    conn.close()

    maunz_handler = MCommandHandler("maunz", maunz_callback)
    bot.add_handler(maunz_handler)