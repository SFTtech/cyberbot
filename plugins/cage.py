"""
module for bernd that posts pictures of the greatest actor of all times.
(rate-limited)
"""
import datetime
import sqlite3
import requests

from matrix_bot_api.mcommand_handler import MCommandHandler

HELP_DESC = ("!cage\t\t\t-\tDisplays an image of the greatest actor of all times.")
UPLOAD_URL = 'https://matrix.org/_matrix/media/r0/upload'
DOWNLOAD_URL = 'https://www.placecage.com/'
RATELIMIT = 3600 # 60 seconds * 60 minutes = 1 hour

"""
register_to() is called by __main__.py for each bot.
"""
def register_to(bot):

    """
    cage_callback() is called whenever someone posts !cage in the chat
    """
    def cage_callback(room, event, data):

        # rate limiting
        formatstring = '%Y-%m-%d %H:%M:%S.%f'
        now = datetime.datetime.now()
        nowstr = now.strftime(formatstring)[:-3]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("select last from {}".format(RATELIMIT_TAB)
                  + " where name = 'cage'")
        laststr = c.fetchall()[0][0]
        last = datetime.datetime.strptime(laststr, formatstring)
        diff = now - last
        diff = diff.seconds

        if diff < RATELIMIT:
            room.send_text('Last Cage was postet not long ago, so... no!')
            conn.close()
            return

        c.execute("update {}".format(RATELIMIT_TAB)
                  + " set last='{}' where name = 'cage'".format(nowstr))
        conn.commit()
        conn.close()

        # actual cage code
        args = event['content']['body'].split()
        # remove the command
        args.pop(0)

        if len(args) < 2:
            r = requests.get(DOWNLOAD_URL + '300/200')
        else:
            r = requests.get(DOWNLOAD_URL + ('/'.join(args)))

        if r:
            img = r.content
            typ = r.headers['content-type']
            print('[i] Downloaded', typ)
            up = room.client.api.media_upload(img, typ)
            print('[i] Uploaded', up)
            uri = up['content_uri']
            room.send_image(uri, 'Hübschlon')
        else:
            room.send_text('Cage ' + DOWNLOAD_URL + ' unavailable :( ')

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        # look if there is an entry for this plugin
        c.execute("select name from {}".format(RATELIMIT_TAB)
                  + " where name = 'cage'")

        # if not, create one
        if c.fetchall() == []:
            c.execute("insert into {}".format(RATELIMIT_TAB)
                      + " values ('cage', '2001-01-01 00:00:00.000')")

    except sqlite3.OperationalError as e:
        # if the table does not exist
        if e.args[0].find('no such table') != -1:
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
