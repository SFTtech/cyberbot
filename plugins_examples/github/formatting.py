import random
from collections import namedtuple

# TODO: escape html


Sender = namedtuple("Sender",["id", "login", "url", "avatar_url"])
Repo = namedtuple("Repository", ["id", "name", "description", "web_url"])



class Formatter:

    def __init__(self,
            event,
            content,
            verbose=False,
            emojis=True,
            asnotice=True):
        self.event = event
        self.content = content
        self.set_formatting_options(verbose,emojis,asnotice)

    def set_formatting_options(self,
            verbose=False,
            emojis=True,
            asnotice=True,):
        self.verbose=verbose
        self.emojis=emojis
        self.asnotice=asnotice


    # =============
    # FORMATTING
    # ============

    def format(self):
        """
        return html representation of event with formatting options
        """
        if self.emojis:
            #animals = "🐶🐺🦊🦝🐱🐱🦁🐯"
            animals = "🐺"
            animal = random.choice(animals)
            return f"{animal} {self.format_content()}"
        else:
            return f"{self.format_content()}"

    def format_content(self):
        pass


    def format_link(self, url, linktext):
        return f"<a href='{url}'>{linktext}</a>"

    def format_sender(self, sender):
        res = f"{sender.login}"
        if sender.url and self.verbose:
            link = self.format_link(f"{sender.url}", sender.login)
            res += f"({link})"
        return res


    def format_repo(self, repo):
        """
        even in a verbose output, we probably do not want to see the description
        """
        if repo.web_url:
            res = self.format_link(repo.web_url, repo.name)
        else:
            res = f"{repo.name}"
        return res


    def format_text_block(self, text, cut=True):
        if cut and text.count("\n") > 3:
            res = "\n".join(text.split("\n")[:3])
            res += "..."
        else:
            res = text
        return f"<pre><code>{res}</code></pre>"



    # =============
    # PARSING
    # ============
    defaultsender = Sender(id="", login="", url="", avatar_url="")
    defaultrepo = Repo(id="", name="", description="", web_url="")

    def get_sender_from_dict(self, senderdict):
        self.defaultsender = Sender(id="", login="", url="", avatar_url="")
        return Sender(
            id=senderdict.get("id",self.defaultsender.id),
            login=senderdict.get("login",self.defaultsender.login),
            url=senderdict.get("url",self.defaultsender.url),
            avatar_url=self.content.get("avatar_url", self.defaultsender.avatar_url)
        )

    def get_sender(self):
        if "sender" not in self.content:
            return self.defaultsender
        senderdict = self.content["sender"]
        return self.get_sender_from_dict(senderdict)


    def get_repo(self):
        if "repository" not in self.content:
            return self.defaultrepo
        repodict = self.content["repository"]
        return Repo(
            id=repodict.get("id", self.defaultrepo.id),
            name=repodict.get("name", self.defaultrepo.name),
            description=repodict.get("description", self.defaultrepo.description),
            web_url=repodict.get("web_url",self.defaultrepo.web_url)
        )



class PushFormatter(Formatter):

    commitattrs =  ["id", "message", "timestamp", "url", "author", "added", "modified", "removed"]
    Commit = namedtuple("Commit", commitattrs)

    defaultcommit = Commit(id="",
            message="",
            timestamp="",
            url="",
            author=Formatter.defaultsender,
            added="",
            modified="",
            removed="")


    def format_branch(self, branchname):
        if self.emojis:
            return f"🌿 {branchname}"
        else:
            return f"branch {branchname}"

    def format_commit(self, commit, href=True, branch=False):
        message = commit.message.split("\n")[0]
        if href and commit.url != "":
            fmt = f"{message}({self.format_link(commit.url,commit.id[:7])})"
        else:
            fmt = f"{message}({commit.id[0:7]})"

        if branch:
            fmt = "⇨ "  + fmt
        return fmt


    def format_commits(self, commits):
        """
        Maybe only print last commit for non verbose?
        """
        return "\n".join(f"<li>{self.format_commit(commit, branch=(i==0))}</li>" for (i,commit) in enumerate(commits))
    
    def get_branch(self):
        ref = self.content.get("ref","")
        return ref.split("/")[-1]

    def commit_from_dict(self, commit):
        attrs = {}
        for attr in self.commitattrs:
            attrs[attr]=commit.get(attr.lower(), getattr(self.defaultcommit,attr))
        return PushFormatter.Commit(**attrs)

    def get_commits(self):
        commitdicts = self.content.get("commits",[])
        commits = []
        for commit in commitdicts:
            commits.append(self.commit_from_dict(commit))
        commits.reverse()
        return commits
                

    def format_content(self):
        repo = self.get_repo()
        fmt_repo = self.format_repo(repo)
        sender = self.get_sender()
        fmt_sender = self.format_sender(sender)
        branch = self.get_branch()
        fmt_branch = self.format_branch(branch)
        commits = self.get_commits()
        fmt_commits = self.format_commits(commits)

        return f'{fmt_sender} pushed to {fmt_branch} of {fmt_repo}:<ul>{fmt_commits}</ul>'


class IssueFormatter(Formatter):

    def format_issue(self, oas, href=True):
        issue = oas.get("issue", {})
        url = issue.get("url","")
        issue_number = issue.get("number","")
        if issue_number:
            issue_number = "#" + str(issue_number)
        title = issue.get("title","Unknown Title")
        res = f"{issue_number} {title}"
        if url and href:
            return self.format_link(url,res)
        else:
            return res

    def format_content(self):
        repo = self.get_repo()
        fmt_repo = self.format_repo(repo)
        sender = self.get_sender()
        fmt_sender = self.format_sender(sender)

        oas = self.content
        action = oas.get("action","did something unknown to")

        new = "new issue" if action == "opened" else "issue"
        fmt_issue = self.format_issue(oas)


        if self.verbose:
            pass #TODO: add more information
        fmt = f"{fmt_sender} {action} {new} {fmt_issue} in {fmt_repo}"
        if action == "opened":
            description = oas.get('description', '')
            if description is not None and description.strip() != "":
                shortendescr = True
                if shortendescr:
                    fmt_description = description
                else:
                    if description.count("\n") > 3:
                        fmt_description = "\n".join(description.split("\n")[:3])
                    fmt_description += "..."
                fmt += f":<br/><pre><code>{fmt_description}</pre></code>"
        return fmt





def format_event(event, content, verbose=False, emojis=True, asnotice=True):
    """
    TODO: change verbose to a verbosity level with multiple (>2) options
    returns None if event shouldn't be printed
    """
    # https://docs.github.com/en/developers/webhooks-and-events/webhook-events-and-payloads
    formatters = {
            "push" : PushFormatter,
            "issues" : IssueFormatter,
            }

    if event in formatters:
        return formatters[event](event, content, verbose, emojis, asnotice).format()
    elif "Confidential" in event:
        return None
    return f"Unknown event received: {event}. Please poke the maintainers."
