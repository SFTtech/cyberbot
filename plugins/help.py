from matrix_bot_api.mcommand_handler import MCommandHandler

HELP_DESC = ("!help\t\t\t\t\t\t-\tDisplay this help message")

def register_to(bot):
    try:
        with open("help_text", "r") as f:
            help_txt = f.read(2048)
    except FileNotFoundError:
        help_txt = ""

    def help_callback(room, event, data):
        room.send_text(help_txt)

    help_handler = MCommandHandler("help", help_callback)
    bot.add_handler(help_handler)

