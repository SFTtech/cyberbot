from matrix_bot_api.mcommand_handler import MCommandHandler

HELP_DESC = "!industry++\t-\tHeralds the dawn of a new industial era"

def register_to(bot):

    def industry_callback(room, event):

        # ignore, if this feature is requested in a private room
        if (event['room_id'] not in TRUSTED_ROOMS):
            room.send_text("This feature is not available in this room")
            return

        # save and update the counterstate in a 'digital_counter' file
        try:
            with open('industry_age', 'r+') as f:
                n = int(f.read(1024))
                f.seek(0)
                n += 1
                f.write(str(n))
        except FileNotFoundError:
            with open('industry_age', 'x') as f:
                n = 0
                f.write(str(n))

        room.send_text("Willkommen im Zeitalter von Industrie {}.0!".format(n))

    industry_handler = MCommandHandler("industry\+\+", industry_callback)
    bot.add_handler(industry_handler)
