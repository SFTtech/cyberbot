from matrix_bot_api.mcommand_handler import MCommandHandler
import feedparser
from threading import Thread
import dbm.ndbm
import time


HELP_DESC = ("(automatic)\t\t-The bot will post changes in rbg gitlab Cybergruppe Group")

class RSSGitlabFeed:

    def __init__(self, bot):
        self.bot = bot
        self.dbmfile = "feed_read.dbm"
        self.thread = Thread(target=self.start, daemon=True)
        self.thread.start()

    def start(self):
        self.check_for_changes()

    def check_for_changes(self):
        rss_token = ENVIRONMENT.get('GITLABRSSTOKEN')
        while True:
            try:
                feed = feedparser.parse(f'https://gitlab.rbg.tum.de/cyber.atom?feed_token={rss_token}')
                self.update_from_feed(feed)
            finally:
                time.sleep(60)

    def update_from_feed(self, feed):
        """
        Generate a list of new entries, and mark the new entries as read
        """
        with dbm.open(self.dbmfile, 'c') as db:
            for entry in reversed(feed['entries']):
                if entry['id'] not in db:
                    self.notify_update(entry)
                    db[entry['id']] = "1"

    def notify_update(self, entry):
        """
        Extract the relevant information from the entry
        If the room is not yet set, it will terminate but also not record any
        recorded change. with is nice.
        """
        # Censor the link that is going to be displayed, if it contains the
        # RSS token - this is a horrible workaround for gitlab
        if ".atom?rss_token=" in entry['link']:
            entry['link'] = "https://gitlab.rbg.de/cyber"

        for rid, r in self.bot.client.get_rooms().items():
            if rid in TRUSTED_ROOMS:
                r.send_notice("{} ({})".format(entry['title'], entry['link']))


def register_to(bot):
    feedreader = RSSGitlabFeed(bot)
