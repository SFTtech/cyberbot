from matrix_bot_api.mcommand_handler import MCommandHandler
import re
import feedparser
import dbm.ndbm
import json
import time
import calendar
import logging

from matrixroom import MatrixRoom
from pprint import pprint

INTERVAL = 5

HELP_DESC = ("!gitlab\t\t\t-\tGitlab Feed Manager/Notifier")

feeds = []

async def register_to(plugin):
    global feeds

    class RSSGitlabFeed:
        """
        Note that last_update holds the highest updated atom feed value,
        which is not in the CEST timeline, so only use the value for comparison
        with other atom feed entries
        """

        def __init__(self, url, feed_token, last_update):
            self.dbmfile = "feed_read.dbm"
            self.feed_token = feed_token
            self.last_update = last_update if last_update is not None else time.gmtime(0)
            self.url = url
            self.task = None


        async def start(self):
            async def check_for_changes():
                try:
                    logging.info(f"GITLAB: fetching {self.url}")
                    feed_url = f'{self.url}?feed_token={self.feed_token}'
                    feed = feedparser.parse(feed_url)
                    if self.last_update == time.gmtime(0):
                        await self.update_from_feed(feed,5)
                    else:
                        await self.update_from_feed(feed)
                except Exception as e:
                    print(e)
            self.task = await plugin.start_task(check_for_changes,INTERVAL)


        async def stop(self):
            if self.task is not None:
                await plugin.stop_task(self.task)
                self.task = None

        async def restart(self):
            self.stop()
            self.start()


        async def update_from_feed(self, feed, last_n=-1):
            if last_n != -1:
                feed['entries'].sort(key=lambda x: x.updated_parsed)
                es = list(reversed(feed['entries']))[:first_n]
            else:
                es = list(reversed(feed['entries']))
            for entry in es:
                if self.last_update is None or entry.updated_parsed > self.last_update:
                    await self.notify_update(entry)

            self.last_update = max(entry.updated_parsed for entry in es)
            await store_feeds()

        async def notify_update(self, entry):
            """
            Extract the relevant information from the entry
            If the room is not yet set, it will terminate but also not record any
            recorded change. with is nice.
            """
            # Censor the link that is going to be displayed, if it contains the
            # RSS token - this is a horrible workaround for gitlab
            re.sub(r'.atom?rss_token=.*', '', entry['link'])
            re.sub(r'.atom?feed_token=.*', '', entry['link'])
            re.sub(r'.atom?personal_token=.*', '', entry['link'])
            await plugin.send_notice(f"{entry['title']} ({entry['link']})")




    subcommands = """gitlab [subcommand] [option1 option2 ...]
Available subcommands:
    addfeed feedurl token   - add a feed with rss_token token
    remfeed feednr          - remove a feed
    listfeeds               - show subscribed feeds and their numbers

    See <a href="https://docs.gitlab.com/ee/api/api_resources.html">here</a> for more information on gitlab feeds.
"""
    #issue                   - show a random issue


    def format_help(text):
        html_text = "<pre><code>" + text + "</code></pre>\n"
        return html_text

    async def show_help():
        formatted_subcommands = format_help(subcommands)
        await plugin.send_html(formatted_subcommands, subcommands)



    async def load_feeds():
        global feeds
        feeds = []
        s = await plugin.kvstore_get_value("feeds")
        if s:
            try:
                k = json.loads(s)
                pprint(k)
                feeds = [ RSSGitlabFeed(url,
                                        feed_token,
                                        time.gmtime(last_update))
                        for (url,feed_token,last_update) in k]
                for feed in feeds:
                    await feed.start()
            except Exception as e:
                logging.warning(str(e))

    async def store_feeds():
        feed_list = [(f.url,f.feed_token, calendar.timegm(f.last_update))
                for f in feeds]
        s = json.dumps(feed_list)
        await plugin.kvstore_set_value("feeds",s)


    async def handle_addfeed(args):
        if len(args) != 2:
            await show_help()
        else:
            url = args[0]
            token = args[1]
            feed = RSSGitlabFeed(url, token, None)
            feeds.append(feed)
            await feed.start()
            await store_feeds()

    async def handle_remfeed(args):
        if len(args) != 1:
            await show_help()
        else:
            try:
                i = int(args[0])
                if i >= len(feeds):
                    await plugin.send_text("Invalid feed number")
                else:
                    await feeds[i].stop()
                    del feeds[i]
                    await store_feeds()
            except ValueError:
                await show_help()
            
    async def handle_listfeeds(args):
        text = "\n".join(f"{i:2} - {feed.url}" for (i,feed) in enumerate(feeds))
        await plugin.send_html(format_help(text))


    #async def handle_issue(args):
    #    pass

    # Echo back the given command
    async def gitlab_callback(room, event):
        args = plugin.extract_args(event)
        args.pop(0)
        if len(args) == 0:
            await show_help()
        elif args[0] == "addfeed":
            args.pop(0)
            await handle_addfeed(args)
        elif args[0] == "remfeed":
            args.pop(0)
            await handle_remfeed(args)
        elif args[0] == "listfeeds":
            args.pop(0)
            await handle_listfeeds(args)
#        elif args[0] == "issue":
#            args.pop(0)
#            await handle_issue(args)
        else:
            await show_help()


    # Add a command handler waiting for the echo command
    await load_feeds()
    gitlab_handler = MCommandHandler("gitlab", gitlab_callback)
    plugin.add_handler(gitlab_handler)

    #feedreader = RSSGitlabFeed(plugin)
    #await feedreader.check_for_changes()
