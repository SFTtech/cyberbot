from matrix_bot_api.mcommand_handler import MCommandHandler

HELP_DESC = "!digital++\t-\tIncrease the digitalization counter (Lindner Style)"

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

        # save and update the counterstate in a 'digital_counter' file
        try:
            with open('digital_counter', 'r+') as f:
                n = int(f.read(1024))
                f.seek(0)
                n += 1
                f.write(str(n))
        except FileNotFoundError:
            with open('digital_counter', 'x') as f:
                n = 0
                f.write(str(n))

        first = get_rank_string(n)
        second = get_rank_string(n+1)
        room.send_text("Digital {}, Bedenken {}.".format(first, second))

    digital_handler = MCommandHandler("digital\+\+", digital_callback)
    bot.add_handler(digital_handler)
