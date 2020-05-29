import random
from collections import namedtuple


User = namedtuple("User",["ID", "name", "username", "email", "avatar_url"])
Project = namedtuple("Project", ["ID", "name", "description", "web_url"])



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
            animals = "🦊"
            animal = random.choice(animals)
            return f"{animal} {self.format_content()}"
        else:
            return f"{self.format_content()}"

    def format_content(self):
        pass


    def format_link(self, url, linktext):
        return f"<a href='{url}'>{linktext}</a>"


    def format_user(self, user):
        """
        Ignore user.username and user.avatar for now
        """
        res = f"{user.name}"
        if user.email and self.verbose:
            link = format_link(f"mailto:{user.email}", user.email)
            res += f"({link})"
        return res


    def format_project(self, project):
        """
        even in a verbose output, we probably do not want to see the description
        """
        if project.web_url:
            res = self.format_link(project.web_url, project.name)
        else:
            res = f"{project.name}"
        return res




    # =============
    # PARSING
    # ============
    defaultuser = User(ID="",name="", username="", email="", avatar_url="")
    defaultproject = Project(ID="", name="", description="", web_url="")

    def get_user_from_dict(self, userdict):
        self.defaultuser = User(ID="",name="", username="", email="", avatar_url="")
        return User(
            ID=self.safe_get_val("id",self.defaultuser.ID,d=userdict),
            name=self.safe_get_val("name",self.defaultuser.name,d=userdict),
            username=self.safe_get_val("username",self.defaultuser.username,d=userdict),
            email=self.safe_get_val("email",self.defaultuser.email,d=userdict),
            avatar_url=self.safe_get_val("avatar_url", self.defaultuser.avatar_url)
        )

    def get_main_user(self):
        """
        In most cases, there is a user key in the root json which contains the
        information. Sometimes it's a little bit more ugly than that and this
        method has to be overriden
        """
        if "user" not in self.content:
            return self.defaultuser
        userdict = self.content["user"]
        return self.get_user_from_dict(userdict)


    def get_project(self):
        if "project" not in self.content:
            return self.defaultproject
        projectdict = self.content["project"]
        return Project(
            ID=self.safe_get_val("id",self.defaultproject.ID,d=projectdict),
            name=self.safe_get_val("name",self.defaultproject.name,d=projectdict),
            description=self.safe_get_val("description",self.defaultproject.description,d=projectdict),
            web_url=self.safe_get_val("web_url",self.defaultproject.web_url,d=projectdict)
        )


    def safe_get_val(self, key,alternative, d=None):
        if d is None:
            d = self.content
        if key in d:
            return d[key]
        else:
            return alternative



class OtherUserFormatter(Formatter):
    """
    Push and Tag Push events have a different way to specifiy the user
    Job Event doesn't contain a user
    """
    def get_main_user(self):
        return User(
            ID=self.safe_get_val("user_id",self.defaultuser.ID),
            name=self.safe_get_val("user_name",self.defaultuser.name),
            username=self.safe_get_val("user_username",self.defaultuser.username),
            email=self.safe_get_val("user_email",self.defaultuser.email),
            avatar_url=self.safe_get_val("user_avatar",self.defaultuser.avatar_url)
        )



class PushFormatter(OtherUserFormatter):

    commitattrs =  ["ID", "message", "title", "timestamp", "url", "author", "added", "modified", "removed"]
    Commit = namedtuple("Commit", commitattrs)

    defaultcommit = Commit(ID="",
            message="",
            title="",
            timestamp="",
            url="",
            author=Formatter.defaultuser,
            added="",
            modified="",
            removed="")


    def format_branch(self, branchname):
        if self.emojis:
            return f"🌿 {branchname}"
        else:
            return f"branch {branchname}"

    def format_commit(self, commit):
        if self.verbose:
            # TODO:
            pass
        else:
            return f"{commit.title} ({self.format_link(commit.url,commit.ID[:7])})"

    def format_commits(self, commits):
        """
        Maybe only print last commit for non verbose?
        """
        return "\n".join(f"<li>{self.format_commit(commit)}</li>" for commit in commits)
    
    def get_branch(self):
        ref = self.safe_get_val("ref","")
        return ref.split("/")[-1]

    def get_commits(self):
        commitdicts = self.safe_get_val("commits",[])
        commits = []
        for commit in commitdicts:
            attrs = {}
            for attr in self.commitattrs:
                if attr == "author" and "author" in commit:
                    attrs["author"] = self.get_user_from_dict(commit['author'])
                else:
                    attrs[attr]=self.safe_get_val(attr.lower(),getattr(self.defaultcommit,attr),d=commit)
            commits.append(PushFormatter.Commit(**attrs))
        return commits
                

    def format_content(self):
        project = self.get_project()
        fmt_project = self.format_project(project)
        user = self.get_main_user()
        fmt_user = self.format_user(user)
        branch = self.get_branch()
        fmt_branch = self.format_branch(branch)
        commits = self.get_commits()
        fmt_commits = self.format_commits(commits)

        return f'{fmt_user} pushed to {fmt_branch} of {fmt_project}:<ul>{fmt_commits}</ul>'




class TagPushFormatter(OtherUserFormatter):

    def format_tag(self, tagname):
        if self.emojis:
            return f"tag 🏷️{tagname}"
        else:
            return f"tag {tagname}"

    def get_tag(self):
        ref = self.safe_get_val("ref","")
        return ref.split("/")[-1]

    def get_verb_preposition(self):
        zeroes = "0000000000000000000000000000000000000000"
        after = self.safe_get_val("after","")
        before = self.safe_get_val("before","")
        if after == zeroes:
            return "deleted","from"
        elif before == zeroes:
            return "pushed new","to"
        else:
            return "changed","in"

    def format_content(self):
        """
        I do not think a distinction has to be made here between verbosity
        levels
        """
        project = self.get_project()
        fmt_project = self.format_project(project)
        user = self.get_main_user()
        fmt_user = self.format_user(user)
        tag = self.get_tag()
        fmt_tag = self.format_tag(tag)
        verb,preposition = self.get_verb_preposition()

        return f"{fmt_user} {verb} remote {fmt_tag} {preposition} {fmt_project}"


class IssueFormatter(Formatter):

    def get_verb_passive(self, action):
        """
        So far I have seen the following verbs: open, reopen, close, update
        """
        # opened and reopened need an ed th the end
        if "open" in action:
            return action + "ed"
        if action == "did something unknown to":
            return atction
        else:
            return action + "d"

    def format_issue(self, oas):
        if self.verbose:
            #TODO
            pass
        else:
            url = self.safe_get_val("url","",d=oas)
            ID = self.safe_get_val("id","",d=oas)
            if ID:
                ID = "#" + str(ID)
            title = self.safe_get_val("title","Unknown Title",d=oas)
            res = f"{ID} {title}"
            if url:
                return self.format_link(url,res)
            else:
                return res

    def format_content(self):
        project = self.get_project()
        fmt_project = self.format_project(project)
        user = self.get_main_user()
        fmt_user = self.format_user(user)

        oas = self.safe_get_val("object_attributes",{})
        action = self.safe_get_val("action","did something unknown to",d=oas)

        verb = self.get_verb_passive(action)
        new = "new issue" if action == "open" else "issue"
        fmt_issue = self.format_issue(oas)

        if self.verbose:
            # TODO
            pass
        else:
            return f"{fmt_user} {verb} {new} {fmt_issue} in {fmt_project}"



def format_event(event, content, verbose=False, emojis=True, asnotice=True):
    """
    TODO: change verbose to a verbosity level with multiple (>2) options
    """
    formatters = {
            "Push Hook" : PushFormatter,
            "Tag Push Hook" : TagPushFormatter,
            "Issue Hook" : IssueFormatter,
            #"Note Hook" : Formatter,
            #"Merge Request Hook" : Formatter,
            #"Wiki Page Hook" : Formatter,
            #"Pipeline Hook" : Formatter,
            #"Job Hook" : Formatter,
            }

    if event in formatters:
        return formatters[event](event, content, verbose, emojis, asnotice).format()
    return f"Unknown event received: {event}. Please poke the maintainers."
#    
#    if event == "Note Hook":
#        user_email = content['user']['email']
#        user_name = content['user']['name']
#        oa = content['object_attributes']
#        noteable_type
#
#    # TODO: note hook
#    # TODO: merge request hook
#    # TODO: wiki hook
#    # TODO: pipeline hook
#    # TODO: job hook
#
