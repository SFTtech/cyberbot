from matrix_bot_api.mregex_handler import MRegexHandler
from random import choice

HELP_DESC = "Hi bernd"


def register_to(bot):
    emojis = ['😍', '💌', '💕', '❤️', '💓', '💘', '💖']

    greetings = ['hey', 'hi', 'ohai', 'heyho', 'cheerio', 'wazzuuuuuup',
                     'greetings', 'yo', 'howdy', 'hiya']

    # Somebody said hi, let's say Hi back
    def hi_callback(room, event):
        if (event['sender'] == '@bernd:stusta.de'):
            greeting = choice(greetings)
            emoji = choice(emojis)
            room.send_text(greeting + ' bernd ' + emoji)

    # Add a regex handler waiting for the word Hi
    hi_handler = MRegexHandler("", hi_callback)
    bot.add_handler(hi_handler)
