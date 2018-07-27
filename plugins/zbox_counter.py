import sqlite3
from matrix_bot_api.mcommand_handler import MCommandHandler

HELP_DESC = "!zbox++\t\t\t-\tCount the number of zboxes required\n"\
            "!zbox\t\t\t-\tShow how many zboxes need to be bought\n"\
            "!0box\t\t\t-\tReset zbox counter after you bought something\n"\

def register_to(bot):

    def zbox_counter(room, event):
        # ignore, if this feature is requested in a private room
        if (event['room_id'] not in TRUSTED_ROOMS):
            room.send_text("This feature is not available in this room")
            return

        # save and update the counterstate in the sqlite database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("update {} set counter=counter+1 where name = 'zbox'"
                  .format(COUNTER_TAB))
        conn.commit()


    def get_counter(room, event):
        """ Give the current counter """
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("select counter from {} where name = 'zbox'"
                  .format(COUNTER_TAB))
        n = c.fetchall()[0][0]
        conn.close()
        if n == 0:
            room.send_text("there are no zboxes planned at the moment :(")
        elif n == 1:
            room.send_text("fm: only one zbox! what can we do with it?")
        elif n == 2:
            room.send_text("fm: lets buy two of them nice zboxes, will we?")
        else:
            room.send_text("fm: buy all {} zboxes! NOW!".format(n))



    def reset_counter(room, event):
        """ set the counter to 0 """
        # ignore, if this feature is requested in a private room
        if (event['room_id'] not in TRUSTED_ROOMS):
            room.send_text("This feature is not available in this room")
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("select counter from {} where name = 'zbox'"
                  .format(COUNTER_TAB))
        n = c.fetchall()[0][0]

        room.send_text("thank you for buying another {} zboxes!"
                       .format(n))

        # save and update the counterstate in the sqlite database
        c.execute("update {} set counter=0 where name = 'zbox'"
                  .format(COUNTER_TAB))
        conn.commit()
        conn.close()




    # initialize sqlite counter entry for this plugin, if not already existing
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("select name from {} where name = 'zbox'"
                       .format(COUNTER_TAB))

        if (cursor.fetchall() == []):
            cursor.execute("insert into {} values ('zbox', 0)"
                           .format(COUNTER_TAB))

    except sqlite3.OperationalError as e:
        if (e.args[0].find('no such table') != -1):
            cursor.execute("create table {} (name text, counter integer)"
                           .format(COUNTER_TAB))

            cursor.execute("insert into {} values ('zbox', 0)"
                           .format(COUNTER_TAB))
        else:
            print("Encountered miscellaneous sqlite error:", e)

    conn.commit()
    conn.close()

    counter_handler = MCommandHandler("zbox\+\+", zbox_counter)
    bot.add_handler(counter_handler)
    get_handler = MCommandHandler("zbox", get_counter)
    bot.add_handler(get_handler)
    reset_handler = MCommandHandler("0box", reset_counter)
    bot.add_handler(reset_handler)
