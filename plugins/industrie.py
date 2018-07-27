import sqlite3
from matrix_bot_api.mcommand_handler import MCommandHandler

HELP_DESC = "!industrie++\t\t-\tHeralds the dawn of a new industrial era"

def register_to(bot):

    def industry_callback(room, event):

        # ignore, if this feature is requested in a private room
        if (event['room_id'] not in TRUSTED_ROOMS):
            room.send_text("This feature is not available in this room")
            return

        # save and update the counterstate in the sqlite database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("update {}".format(COUNTER_TAB)
                  + " set counter=counter+1 where name = 'industrie'")
        conn.commit()
        c.execute("select counter from {}".format(COUNTER_TAB)
                  + " where name = 'industrie'")
        n = c.fetchall()[0][0]
        conn.close()

        room.send_text("Willkommen im Zeitalter von Industrie {}.0!".format(n))


    # initialize sqlite counter entry for this plugin, if not already existing
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        c.execute("select name from {}".format(COUNTER_TAB)
                  + " where name = 'industrie'")

        if (c.fetchall() == []):
            c.execute("insert into {}".format(COUNTER_TAB)
                      + " values ('industrie', 0)")

    except sqlite3.OperationalError as e:
        if (e.args[0].find('no such table') != -1):
            c.execute("create table {}".format(COUNTER_TAB)
                      + " (name text, counter integer)")

            c.execute("insert into {}".format(COUNTER_TAB)
                      + " values ('industrie', 0)")
        else:
            print("Encountered miscellaneous sqlite error:", e)

    conn.commit()
    conn.close()

    industry_handler = MCommandHandler("industrie\+\+", industry_callback)
    bot.add_handler(industry_handler)
