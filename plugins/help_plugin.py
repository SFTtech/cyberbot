from matrix_bot_api.mcommand_handler import MCommandHandler

HELP_DESC = ("!help\t\t\t-\tDisplay this help message")

def register_to(plugin):
    def format_help(text):
        html_text = "<pre><code>" + text + "</code></pre>\n"
        return html_text

    async def help_callback(room, event):
        available = plugin.mroom.bot.available_plugins
        pluginnames = [p.pluginname for p in plugin.mroom.plugins]
        help_txt = "\n".join(available[pname] for pname in pluginnames)
        help_txt += '''
        For more information, look at the wiki page at <a href="">TODO</a>
        '''
        formatted_help = format_help(help_txt)
        #print(dir(room))
        await room.send_html(formatted_help, help_txt)

    help_handler = MCommandHandler("help", help_callback)
    plugin.add_handler(help_handler)
