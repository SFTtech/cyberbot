from matrix_bot_api.mcommand_handler import MCommandHandler
from random import choice, randint


HELP_DESC = "!oop\t\t\t\t\t\t-\tTurns your argument into a class."

def register_to(bot):
    oop_names = ['Factory', 'Manager', 'Handler', 'Class', 'Object', 'Producer', 'Actor', 'Mirror']

    def oop_callback(room, event):
        args = event['content']['body'].split()

        s = args[1]
        i = randint(3,9)
        
        while (i > 0):
            s += choice(oop_names)
            i -= 1

        room.send_text('class ' + s)

    oop_handler = MCommandHandler("oop", oop_callback)
    bot.add_handler(oop_handler)
