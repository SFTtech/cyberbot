import sqlite3
import string
from matrix_bot_api.mcommand_handler import MCommandHandler
from matrix_bot_api.mregex_handler import MRegexHandler

HELP_DESC = ("!correct FROM TO\t\t\t-\tAdd a new political correction handler\n"
             "!incorrect FROM\t\t\t\t-\tRemove given political correction handler\n")


class PoliticalCorrectness:

    def __init__(self, bot):
        self.bot = bot

        # init the database connnection
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        try:
            c.execute("select * from {}".format(CORRECTION_TAB))

            res = c.fetchall()
            if not res:
                print("[i] Correction table found empty.")

            # register a regex handler for every corretion entry in the database
            for c in res:
                polcor_handler = MRegexHandler(c[0], self.generic_correction_callback)
                self.bot.add_handler(polcor_handler, (c[0], c[1]))

        except sqlite3.OperationalError as e:
            print("[i] Correction table not found. Creating...")
            if (e.args[0].find('no such table') != -1):
                c.execute("create table {} (word text, correct_word text)".format(CORRECTION_TAB))
            else:
                print("Encountered miscellaneous sqlite error:", e)

        conn.commit()
        conn.close()

        correct_handler = MCommandHandler("correct", self.correct_callback)
        incorrect_handler = MCommandHandler("incorrect", self.incorrect_callback)
        self.bot.add_handler(correct_handler)
        self.bot.add_handler(incorrect_handler)


    def generic_correction_callback(self, room, event, data):
        word = data[0]
        corrected_word = data[1]
        msg = event['content']['body'].replace(word, corrected_word)

        text = str(event['sender'] + ': '
                   + "Bei '{}' handelt es sich um Hasssprech.".format(word)
                   + " Solche Ausdrücke verwenden wir hier nicht."
                   + " Die politisch korrekte Aussage wäre:\n\n\""
                   + msg + "\"")

        room.send_text(text)

    def incorrect_callback(self, room, event, data):
        args = event['content']['body'].split()
        word = args[1]

        # try to find the given correction
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("select * from {} where word = '{}'".format(CORRECTION_TAB, word))

        res = c.fetchall()

        if not res:
            room.send_text("The given word couldn't be found in the database.")
            conn.close()
            return

        # delete the entry from the database
        c.execute("delete from {} where word = '{}'".format(CORRECTION_TAB, word))
        conn.commit()

        # unregister the corresponding regex handler
        handlers = self.bot.get_handler(word)
        for h in handlers:
            self.bot.remove_handler(h)

        conn.close()
        room.send_text("Removed the given correction from the database.")

    def correct_callback(self, room, event, data):

        word = ""
        correct_word = ""

        # ignore, if this feature is requested in a private room
        if (event['room_id'] not in TRUSTED_ROOMS):
            room.send_text("This feature is not available in this room")
            return

        # parse arguments
        args = event['content']['body'].split()

        try:
            word = args[1]
            correct_word = args[2]
        except IndexError as e:
            room.send_text("The given arguments could not be parsed.")
            return

        # word sanity checking
        wset = set(word)
        cwset = set(correct_word)
        aset = set(string.ascii_letters).union(set('äöüÄÖÜß'))

        if not wset <= aset:
            room.send_text("Political Correctness is only supported for chars "
                           + "[a-z]äöüß[A-Z]ÄÖÜ.")
            return

        if word == correct_word:
            room.send_text("Corrections are only accepted for differing words.")
            return

        # try to insert the given handle into the correctness database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("select * from {} where word = '{}'".format(CORRECTION_TAB,
                                                              word))
        res = c.fetchall()

        if res == []:
            c.execute("insert into {} values ('{}', '{}')".format(CORRECTION_TAB, word, correct_word))
            conn.commit()

        elif res[0][1] == correct_word:
            room.send_text("The requested correction already exists in the"
                           " database.")
            conn.close()
            return

        elif res[0][1] != correct_word:
            c.execute("update {} set correct_word='{}' where word = '{}'".format(CORRECTION_TAB, correct_word, word))
            conn.commit()

        # register a regex handler for the newly inserted word
        polcor_handler = MRegexHandler(word, self.generic_correction_callback)
        self.bot.add_handler(polcor_handler, (word, correct_word))

        conn.close()
        room.send_text("Successfully updated correction database.")

def register_to(bot):
    political_correctness = PoliticalCorrectness(bot)
