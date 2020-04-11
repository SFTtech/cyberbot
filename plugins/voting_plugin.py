from pprint import pprint
from collections import defaultdict
import json
import time
from datetime import datetime

HELP_DESC = ("!voting\t\t\t-\t(WIP)Voting subcommands\n")

"""
TODO: add deadline support via asyncio tasks
"""





async def register_to(plugin):
    subcommands = """Available subcommands:
    DURATION DOES NOT WORK YET!! POLLS HAVE TO BE MANUALLY CLOSED!!

    perm      [admins|all]                                  - change who can create a poll
    addpoll   [--duration seconds] NAME option1 option2 ... - add a poll
    listpolls                                               - list running polls
    closepoll pollname                                      - close a poll (only the creator and admins can close a poll)
    vote      pollname option                               - vote on a poll

    Quote arguments if they contain whitespace
    Example: !voting addpoll best_botname Roboter Terminator 'Frank Zappa'
"""


    class Poll:
        def __init__(self,
                creator,
                name,
                options,
                duration=None,
                votes=defaultdict(int),
                voted=[],
                creation=None):
            self.creator = creator
            self.name = name
            self.options = options
            self.duration = duration

            if not creation:
                self.creation = int(time.time())
            else:
                self.creation = creation

            self.voted = voted
            self.votes = votes


        async def add_vote(self, user, option):
            if option in self.options and user not in self.voted:
                self.votes[option] += 1;
                self.voted.append(user)
                return True
            else:
                return False

        def __str__(self):
            res = f"Pollname: {self.name}\nTotal votes: {len(self.voted)}"
            res += f"\nCreated by {self.creator} on {datetime.fromtimestamp(self.creation)}"
            if self.duration:
                res += f"\nduration: {self.duration}, time left: {None}"
            res += f"\n#votes    option"
            opts = reversed(sorted(self.options, key=lambda o:self.votes[o]))
            for option in opts:
                nrvotes = self.votes[option]
                strnr = str(nrvotes).rjust(6," ")
                res += f"\n{strnr}          {option}"
            return res


        def to_list(self):
            votes = [self.votes[o] for o in self.options]
            return [self.name,self.creator,str(self.duration),self.voted,self.options,votes, self.creation]

        def from_list(l):
            print(l)
            name,creator,duration,voted,options,votes,creation = l
            vs = defaultdict(int)
            if duration == "None":
                duration = None
            else:
                duration = int(duration)
            for (o,v) in zip(options,votes):
                vs[o] = v
            p = Poll(creator, name, options, duration, vs, voted, creation)
            return p
            




    class Voting:

        def __init__(self, active_polls=[], onlyadmincreators=False):
            self.active_polls = active_polls
            self.onlyadmincreators = onlyadmincreators

        @classmethod
        async def load(cls):
            keys = await plugin.kvstore_get_keys()

            if "active_polls" not in keys:
                active_polls = []
            else:
                j = json.loads(await plugin.kvstore_get_value("active_polls"))
                active_polls = [Poll.from_list(l) for l in j]

            if "onlyadmincreators" not in keys:
                onlyadmincreators = False
            else:
                onlyadmincreators = bool(await plugin.kvstore_get_value("onlyadmincreators"))

            v = Voting(active_polls,onlyadmincreators)
            return v


        async def save(self):
            active_polls = [poll.to_list() for poll in self.active_polls]
            j = json.dumps(active_polls)
            await plugin.kvstore_set_value("active_polls", j)
            await plugin.kvstore_set_value("onlyadmincreators", str(self.onlyadmincreators))


        def add_poll(self, creator, name, options, duration=None):
            if any(poll.name == name for poll in self.active_polls):
                return None
            p = Poll(creator,name,options,duration)
            self.active_polls.append(p)
            return p

        def get_poll(self, name):
            p = [(i,poll) for (i,poll) in enumerate(self.active_polls) if poll.name == name]
            if not p:
                return None
            return p[0]
        
        async def close_poll(self, name):
            p = self.get_poll(name)
            if not p:
                return None
            else:
                i,poll = p
                del self.active_polls[i]
                return poll

        async def vote(self, name, option, sender):
            p = self.get_poll(name)
            if not p:
                return False
            i,poll = p
            return await poll.add_vote(sender, option)
            


        def __str__(self):
            res = f"number of running polls: {len(self.active_polls)}\n\n"
            return res + "\n\n\n".join([*(str(poll) for poll in self.active_polls)])


            

    def format_help(text):
        html_text = "<pre><code>" + text + "</code></pre>\n"
        return html_text
    
    async def help():
        formatted_subcommands = format_help(subcommands)
        await plugin.send_html(formatted_subcommands, subcommands)

    # Echo back the given command
    async def voting_callback(room, event):
        print(room.nio_room.users.get(event.sender).power_level)
        args = plugin.extract_args(event)
        args.pop(0)
        #await plugin.send_text(event['sender'] + ': ' + ' '.join(args))
        if len(args) == 0:
            await help()
        elif args[0] == "perm":
            if len(args) != 2 or args[1] not in ["admins", "all"]:
                await help()
            else:
                if args[1] == "admins":
                    await plugin.send_text("Thank you. Only admins can create polls now.")
                    voting.onlyadmincreators = True
                else:
                    await plugin.send_text("Thank you. Everybody can create polls now.")
                    voting.onlyadmincreators = True
                await voting.save()
        elif args[0] == "addpoll":
            if len(args) < 3:
                await help()
            elif voting.onlyadmincreators \
                    and room.nio_room.users.get(event.sender).power_level != 100:
                        await plugin.send_text("You don't have permissions to create polls")
            else:
                if args[1] == "--duration":
                    duration = int(args[2])
                    args = args[2:]
                else:
                    duration = None
                name = args[1]
                options = args[2:]
                if len([o1 for o1 in options for o2 in options if o1 == o2]) != len(options):
                    await plugin.send_text("Invalid: two options have the same name")
                else:
                    poll = voting.add_poll(event.sender, name, options, duration)
                    if poll:
                        await voting.save()
                        await plugin.send_text(f"Sucessfully created poll:\n{poll}")
                    else:
                        await plugin.send_text("There was an error creating the poll.")
        elif args[0] == "listpolls":
            await plugin.send_text(f"{voting}")
        elif args[0] == "closepoll":
            if len(args) != 2:
                await help()
            else:
                p = await voting.close_poll(args[1])
                if p:
                    await plugin.send_text(f"Results\n=====================\n{p}")
                    await voting.save()
                else:
                    pass

        elif args[0] == "vote":
            if len(args) != 3:
                await help()
            name = args[1]
            option = args[2]
            if not await voting.vote(name, option, event.sender):
                plugin.send_text("Error. Check that you haven't voted already and that the poll exists")
            await voting.save()




    global voting
    voting = await Voting.load()
    # Add a command handler waiting for the echo command
    voting_handler = plugin.CommandHandler("voting", voting_callback)
    plugin.add_handler(voting_handler)

