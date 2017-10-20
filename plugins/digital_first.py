import sqlite3
from matrix_bot_api.mcommand_handler import MCommandHandler

HELP_DESC = ("!digital++\t\t\t\t\t-\tIncrease the digitalization counter"
             " (Lindner Style)")

def register_to(bot):

    def get_rank_string(n):

        small_ranks = ['zeroth', 'first', 'second', 'third', 'fourth', 'fifth',
                       'sixth', 'seventh', 'eighth', 'ninth', 'tenth',
                       'eleventh']

        if (n >= 0 and n <= 11):
            return small_ranks[n]
        else:
            return str(n)+"th"

    def digital_callback(room, event):

        # ignore, if this feature is requested in a private room
        if (event['room_id'] not in TRUSTED_ROOMS):
            room.send_text("This feature is not available in this room")
            return

        # save and update the counterstate in the counter database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("update {}".format(COUNTER_TAB)
                  + " set counter=counter+1 where name = 'digital'")
        conn.commit()
        c.execute("select counter from {}".format(COUNTER_TAB)
                  + " where name = 'digital'")
        n = c.fetchall()[0][0]
        conn.close()

        first = get_rank_string(n)
        second = get_rank_string(n+1)
        room.send_text("Digital {}, Bedenken {}.".format(first, second))


    # initialize sqlite counter entry for this plugin, if not already existing
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        c.execute("select name from {}".format(COUNTER_TAB)
                  + " where name = 'digital'")

        if (c.fetchall() == []):
            c.execute("insert into {}".format(COUNTER_TAB)
                      + " values ('digital', 0)")

    except sqlite3.OperationalError as e:
        if (e.args[0].find('no such table') != -1):
            c.execute("create table {}".format(COUNTER_TAB)
                      + " (name text, counter integer)")

            c.execute("insert into {}".format(COUNTER_TAB)
                      + " values ('digital', 0)")
        else:
            print("Encountered miscellaneous sqlite error:", e)

    conn.commit()
    conn.close()

    digital_handler = MCommandHandler("digital\+\+", digital_callback)
    bot.add_handler(digital_handler)
