from matrix_bot_api.mregex_handler import MRegexHandler
from random import randint

HELP_DESC = "(automatic)\t\tThe bot will greet back people, posting salutations"

def register_to(bot):

    # Somebody said hi, let's say Hi back
    def hi_callback(room, event):
        greetings = ['hey', 'hi', 'ohai', 'heyho', 'cheerio', 'wazzuuuuuup',
                     'greetings', 'yo', 'howdy', 'hiya']
        jabberings = ['how are ya?', 'how\'s it going?', 'how\'s life?',
                      'nice to see you', 'it\'s been a while', 'alright, mate?',
                      'what\'s up?']

        greeting = greetings[randint(0, len(greetings)-1)]
        jabbering = jabberings[randint(0, len(jabberings)-1)]

        room.send_text(greeting + ' ' + event['sender'] + '. ' + jabbering)

    # Add a regex handler waiting for the word Hi
    hi_handler = MRegexHandler("(\s+|^)(([sS]er(v[ua])?s)|" +
                               "([[M|m]oin])+|" +
                               "(([oOaA]?)" +
                               "((bend)|([hH](ey(ho)?|i|ai|ello|allo)))))" +
                               "(\s+|$)",
                                hi_callback)
    bot.add_handler(hi_handler)
