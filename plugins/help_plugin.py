
HELP_DESC = ("!help\t\t\t-\tDisplay this help message\n")

async def register_to(plugin):
    def format_help(text):
        html_text = "<pre><code>" + text + "</code></pre>\n"
        return html_text

    async def help_callback(room, event):
        available = plugin.mroom.bot.available_plugins
        pluginnames = [p.pluginname for p in plugin.mroom.plugins]
        help_txt = "\n".join(available[pname].strip() for pname in pluginnames)
        help_txt += '''

        For more information, look at the wiki page at <a href="">TODO</a>
        '''
        formatted_help = format_help(help_txt)
        #print(dir(room))
        await plugin.send_html(formatted_help, help_txt)

    help_handler = plugin.CommandHandler("help", help_callback)
    plugin.add_handler(help_handler)
