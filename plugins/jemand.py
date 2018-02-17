# coding=utf-8
"""
the jemand plugin automatically replies when someone writes 'jemand™' in the
room, and saves the task that was assigned to 'jemand™'
"""
import random
import sqlite3
from matrix_bot_api.mregex_handler import MRegexHandler
from matrix_bot_api.mcommand_handler import MCommandHandler

HELP_DESC = ("(automatic)\t\tThe bot replaces 'jemand™' in a sentence with a "
             "random room member\n"
             "!tasks\t\t\t\t\t - shows tasks that were assigned to jemand™")

TABLE_NAME = "tasks"

def register_to(bot):
    """
    register_to() gets called from bernd/__main__.py for every file in plugins/
    """

    # Echo back the given command
    def jemand_callback(room, event):
        """
        jemand_callback() is executed when someone mentions 'jemand™'
        """

        msg = event['content']['body']

        # save the task to the database
        conn = sqlite3.connect(DB_PATH)
        curs = conn.cursor()
        curs.execute("insert into" + TABLE_NAME + "(?)", msg)
        conn.commit()
        conn.close()

        members = room.get_joined_members()
        jemand = random.choice(list(members))
        msg = msg.replace("jemand™", jemand.user_id)
        room.send_text(msg)


    def tasks_callback(room, event):
        """
        tasks_callback gets called whenever someone says "!tasks" in a room
        """
        conn = sqlite3.connect(DB_PATH)
        curs = conn.cursor()
        results = curs.execute("select task from {}".format(TABLE_NAME))
        conn.commit()
        conn.close()

        msg = ""
        for result in results:
            msg = msg + result + "\n"

        room.send_text(msg)


    conn = sqlite3.connect(DB_PATH)
    curs = conn.cursor()

    try:
        curs.execute("select task from {}".format(TABLE_NAME))
    except sqlite3.OperationalError as error:
        if error.args[0].find('no such table') != -1:
            curs.execute("create table {}".format(TABLE_NAME)
                         + " (task text)")
        else:
            print("Encountered miscellaneous sqlite error:", error)

    conn.commit()
    conn.close()


    # Add a command handler waiting for the commands
    jemand_handler = MRegexHandler("jemand™", jemand_callback)
    bot.add_handler(jemand_handler)
    tasks_handler = MCommandHandler("tasks", tasks_callback)
    bot.add_handler(tasks_handler)
