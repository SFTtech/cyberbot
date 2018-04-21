from matrix_bot_api.mcommand_handler import MCommandHandler
import feedparser
from random import choice

HELP_DESC = ("!issue\t\t\t\t\t\t-\tThe bot will post a random open issue from the stustanet group")

def register_to(bot):

    def issue_callback(room, event, data):

        # get the online feed
        feed = feedparser.parse('https://gitlab.stusta.de/groups/stustanet/-/issues.atom?rss_token=yjcgz4jbZHsph-sL3tq1&state=opened')

        # choose one isse randomly
        issue = choice(feed['entries'])

        # get the information about the issue
        title = issue['title']
        description = issue['content'][0]['value']
        link = issue['link']
        project = link.split('/')[4]

        #send the issue to the chat!
        room.send_text("Here is an issue for you to work on:\n"+
                       project + ": " + title + "\n" +
                       description + "\n" +
                       link)

    issue_handler = MCommandHandler("issue", issue_callback)
    bot.add_handler(issue_handler)
