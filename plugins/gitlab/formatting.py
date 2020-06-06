import random
from collections import namedtuple

# TODO: escape html


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

    def format_commit(self, commit, href=True):
        if self.verbose:
            # TODO:
            pass
        else:
            if href:
                return f"{commit.title} ({self.format_link(commit.url,commit.ID[:7])})"
            else:
                return f"{commit.title} ({commit.ID[0:7]})"

    def format_commits(self, commits):
        """
        Maybe only print last commit for non verbose?
        """
        return "\n".join(f"<li>{self.format_commit(commit)}</li>" for commit in commits)
    
    def get_branch(self):
        ref = self.safe_get_val("ref","")
        return ref.split("/")[-1]

    def commit_from_dict(self, commit):
        attrs = {}
        for attr in self.commitattrs:
            if attr == "author" and "author" in commit:
                attrs["author"] = self.get_user_from_dict(commit['author'])
            else:
                attrs[attr]=self.safe_get_val(attr.lower(),getattr(self.defaultcommit,attr),d=commit)
        return PushFormatter.Commit(**attrs)

    def get_commits(self):
        commitdicts = self.safe_get_val("commits",[])
        commits = []
        for commit in commitdicts:
            commits.append(commit_from_dict(commit))
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
            return action
        else:
            return action + "d"

    def format_issue(self, oas, href=True):
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
            if url and href:
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


class NoteFormatter(Formatter):
    """
    four types of comments: commit, merge request, issue, code snippet
    https://docs.gitlab.com/ee/user/project/integrations/webhooks.html#comment-events
    """

    def format_target(self, oas):
        if "noteable_type" not in oas:
            return f"Received invalid Comment Type (no noteable_type field in object_attributes)"
        comment_type = oas["noteable_type"]
        comment_url = self.safe_get_val("url", "https://example.com", d=oas)
        if comment_type == "Issue":
            comment_target = IssueFormatter(self.event, self.content, self.verbose, self.emojis, self.asnotice).format_issue(self.safe_get_val("issue", {}), href=False)
            fmt_comment_target = self.format_link(comment_url ,comment_target)
        elif comment_type == "Snippet":
            snips = self.safe_get_val("snippet", {})
            snippet_title = self.safe_get_val("title", "", d=snips)
            snippet_content = self.safe_get_val("content", "", d=snips)
            snippet_fname = self.safe_get_val("file_name", "", d=snips)
            comment_target = f"{snippet_title} ({snippet_fname})"
            fmt_comment_target = "snippet " + self.format_link(comment_url ,comment_target)
        elif comment_type == "Commit":
            pf = PushFormatter(self.event, self.content, self.verbose, self.emojis, self.asnotice)
            commit = pf.commit_from_dict(self.safe_get_val("commit", {}))
            comment_target = pf.format_commit(commit, href=False)
            fmt_comment_target = self.format_link(comment_url ,comment_target)
            print(fmt_comment_target)
        elif comment_type == "MergeRequest":
            mr = self.safe_get_val("merge_request",{})
            comment_target = MergeFormatter.format_mr(mr, href=False)
            fmt_comment_target = self.format_link(comment_url ,comment_target)
        else:
            fmt_comment_target = f"Unknown Commen Target {comment_type}"
        return fmt_comment_target


    def format_content(self):
        shortendescr = True
        user = self.get_main_user()
        fmt_user = self.format_user(user)
        project = self.get_project()
        fmt_project = self.format_project(project)

        oas = self.safe_get_val("object_attributes",{})

        fmt_target = self.format_target(oas)
        note = self.safe_get_val("note", "", d=oas)
        if self.verbose:
            fmt_note = note
        else:
            if note.count("\n") > 3:
                fmt_note = "\n".join(note.split("\n")[:3])
                fmt_note += "..."
            else:
                fmt_note = note

        return f"{fmt_user} commented on {fmt_target} in {fmt_project}:<br/><pre><code>{fmt_note}</pre></code>"




class MergeFormatter(Formatter):

    def get_verb_passive(self, action):
        """
        So far I have seen the following verbs: open, reopen, close, update
        """
        # opened and reopened need an ed th the end
        if "open" in action:
            return action + "ed"
        if action == "did something unknown to":
            return action
        else:
            return action + "d"

    def format_mr(oas, href=True):
        def safe_get_val(a,b,d):
            if a in d:
                return d[a]
            else:
                return b
        iid = safe_get_val("iid","",d=oas)
        url = safe_get_val("url", "", d=oas)
        source = safe_get_val("source", {}, d=oas)
        target = safe_get_val("target", {}, d=oas)

        source_p =  safe_get_val("path_with_namespace","",d=source)
        source_branch =  safe_get_val("source_branch","",d=oas)
        target_p =  safe_get_val("path_with_namespace","",d=target)
        target_branch =  safe_get_val("target_branch","",d=oas)
        if source_p == target_p:
            fmt_mr = f"Merge Request !{iid} from branch {source_branch} to {target_branch}"
        else:
            fmt_mr = f"Merge Request !{iid} from {source_p}/{source_branch} to {target_p}/{target_branch}"
        if href:
            return f"<a href='{url}'>{fmt_mr}</a>"
        else:
            return fmt_mr

    def format_content(self):
        shortendescr = True

        user = self.get_main_user()
        fmt_user = self.format_user(user)

        project = self.get_project()
        fmt_project = self.format_project(project)

        oas = self.safe_get_val("object_attributes",{})

        fmt_mr = MergeFormatter.format_mr(oas)

        action =  self.safe_get_val("action", "did something unknown to",d=oas)
        verb = self.get_verb_passive(action)


        description = self.safe_get_val("note", "", d=oas)
        if shortendescr:
            fmt_description = description
        else:
            if description.count("\n") > 3:
                fmt_description = "\n".join(description.split("\n")[:3])
                fmt_description += "..."

        if self.verbose and action == "open":
            return f"{fmt_user} {verb} {fmt_mr} in {fmt_project}:<br/><pre><code>{fmt_description}</pre></code>"
        else:
            return f"{fmt_user} {verb} {fmt_mr} in {fmt_project}"



class WikiFormatter(Formatter):

    def get_verb_passive(self, action):
        """
        So far I have seen the following verbs: create, update, delete
        """
        # opened and reopened need an ed th the end
        if action == "did something unknown to":
            return action
        else:
            return action + "d"

    def format_wiki_page(self, oas, href=True):
        url = self.safe_get_val("web_url", "", d=oas)
        title = self.safe_get_val("title", "", d=oas)
        fmt = f"Wiki Page {title}"
        if href:
            return self.format_link(url, fmt)
        else:
            return fmt

    def format_content(self):
        shortendescr = True

        user = self.get_main_user()
        fmt_user = self.format_user(user)

        project = self.get_project()
        fmt_project = self.format_project(project)


        oas = self.safe_get_val("object_attributes",{})
        fmt_wiki = self.format_wiki_page(oas)


        action =  self.safe_get_val("action", "did something unknown to",d=oas)
        verb = self.get_verb_passive(action)

        return f"{fmt_user} {verb} {fmt_wiki} in {fmt_project}"


def format_event(event, content, verbose=False, emojis=True, asnotice=True):
    """
    TODO: change verbose to a verbosity level with multiple (>2) options
    """
    formatters = {
            "Push Hook" : PushFormatter,
            "Tag Push Hook" : TagPushFormatter,
            "Issue Hook" : IssueFormatter,
            "Note Hook" : NoteFormatter,
            "Merge Request Hook" : MergeFormatter,
            "Wiki Page Hook" : WikiFormatter,
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
