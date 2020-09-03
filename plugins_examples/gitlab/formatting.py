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
            link = self.format_link(f"mailto:{user.email}", user.email)
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


    def format_text_block(self, text, cut=True):
        if cut and text.count("\n") > 3:
            res = "\n".join(text.split("\n")[:3])
            res += "..."
        else:
            res = text
        return f"<pre><code>{res}</code></pre>"


    def get_verb_passive(self, action):
        """
        So far I have seen the following verbs: open, reopen, close, update, approve
        """
        # opened and reopened need an ed th the end
        if action == "did something unknown to":
            return action
        elif action.endswith("ed"):
            return action
        elif action.endswith("e"):
            return action + "d"
        else:
            return action + "ed"




    # =============
    # PARSING
    # ============
    defaultuser = User(ID="",name="", username="", email="", avatar_url="")
    defaultproject = Project(ID="", name="", description="", web_url="")

    def get_user_from_dict(self, userdict):
        self.defaultuser = User(ID="",name="", username="", email="", avatar_url="")
        return User(
            ID=userdict.get("id",self.defaultuser.ID),
            name=userdict.get("name",self.defaultuser.name),
            username=userdict.get("username",self.defaultuser.username),
            email=userdict.get("email",self.defaultuser.email),
            avatar_url=self.content.get("avatar_url", self.defaultuser.avatar_url)
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
            ID=projectdict.get("id",self.defaultproject.ID),
            name=projectdict.get("name",self.defaultproject.name),
            description=projectdict.get("description",self.defaultproject.description),
            web_url=projectdict.get("web_url",self.defaultproject.web_url)
        )




class OtherUserFormatter(Formatter):
    """
    Push and Tag Push events have a different way to specifiy the user
    Job Event doesn't contain a user
    """
    def get_main_user(self):
        return User(
            ID=self.content.get("user_id",self.defaultuser.ID),
            name=self.content.get("user_name",self.defaultuser.name),
            username=self.content.get("user_username",self.defaultuser.username),
            email=self.content.get("user_email",self.defaultuser.email),
            avatar_url=self.content.get("user_avatar",self.defaultuser.avatar_url)
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

    def format_commit(self, commit, href=True, branch=False):
        if self.verbose:
            fmt_message = self.format_text_block(commit.message, cut=True)
            if href and commit.url != "":
                fmt = f"{commit.title} ({self.format_link(commit.url,commit.ID[:7])})</br>{fmt_message}"
            else:
                fmt = f"{commit.title} ({commit.ID[0:7]})</br>{fmt_message}"
        else:
            if href and commit.url != "":
                fmt = f"{commit.title} ({self.format_link(commit.url,commit.ID[:7])})"
            else:
                fmt = f"{commit.title} ({commit.ID[0:7]})"
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
            if attr == "author" and "author" in commit:
                attrs["author"] = self.get_user_from_dict(commit['author'])
            else:
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
        ref = self.content.get("ref","")
        return ref.split("/")[-1]

    def get_verb_preposition(self):
        zeroes = "0000000000000000000000000000000000000000"
        after = self.content.get("after","")
        before = self.content.get("before","")
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

    def format_issue(self, oas, href=True):
        url = oas.get("url","")
        IID = oas.get("iid","")
        if IID:
            IID = "#" + str(IID)
        title = oas.get("title","Unknown Title")
        res = f"{IID} {title}"
        if url and href:
            return self.format_link(url,res)
        else:
            return res

    def format_content(self):
        project = self.get_project()
        fmt_project = self.format_project(project)
        user = self.get_main_user()
        fmt_user = self.format_user(user)

        oas = self.content.get("object_attributes",{})
        action = oas.get("action","did something unknown to")

        verb = self.get_verb_passive(action)
        new = "new issue" if action == "open" else "issue"
        fmt_issue = self.format_issue(oas)


        if self.verbose:
            pass #TODO: add more information
        fmt = f"{fmt_user} {verb} {new} {fmt_issue} in {fmt_project}"
        if action == "open":
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



class NoteFormatter(Formatter):
    """
    four types of comments: commit, merge request, issue, code snippet
    https://docs.gitlab.com/ee/user/project/integrations/webhooks.html#comment-events
    """

    def format_target(self, oas):
        if "noteable_type" not in oas:
            return f"Received invalid Comment Type (no noteable_type field in object_attributes)"
        comment_type = oas["noteable_type"]
        comment_url = oas.get("url", "https://example.com")
        if comment_type == "Issue":
            comment_target = IssueFormatter(self.event, self.content,
                    self.verbose, self.emojis, self.asnotice).format_issue(self.content.get("issue", {}), href=False)
            fmt_comment_target = self.format_link(comment_url ,comment_target)
        elif comment_type == "Snippet":
            snips = self.content.get("snippet", {})
            snippet_title = snips.get("title", "")
            snippet_content = snips.get("content", "")
            snippet_fname = snips.get("file_name", "")
            comment_target = f"{snippet_title} ({snippet_fname})"
            fmt_comment_target = "snippet " + self.format_link(comment_url ,comment_target)
        elif comment_type == "Commit":
            pf = PushFormatter(self.event, self.content, self.verbose, self.emojis, self.asnotice)
            commit = pf.commit_from_dict(self.content.get("commit", {}))
            comment_target = pf.format_commit(commit, href=False)
            fmt_comment_target = self.format_link(comment_url ,comment_target)
            print(fmt_comment_target)
        elif comment_type == "MergeRequest":
            mr = self.content.get("merge_request",{})
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

        oas = self.content.get("object_attributes",{})

        fmt_target = self.format_target(oas)
        note = oas.get("note", "")
        fmt_note = self.format_text_block(note, cut=(not self.verbose))

        return f"{fmt_user} commented on {fmt_target} in {fmt_project}:<br/>{fmt_note}"




class MergeFormatter(Formatter):

    def format_mr(oas, href=True):
        iid = oas.get("iid","")
        url = oas.get("url", "")
        source = oas.get("source", {})
        target = oas.get("target", {})

        source_p =  source.get("path_with_namespace","")
        source_branch =  oas.get("source_branch","")
        target_p =  target.get("path_with_namespace","")
        target_branch =  oas.get("target_branch","")
        if source_p == target_p:
            fmt_mr = f"Merge Request !{iid} from branch {source_branch} to {target_branch}"
        else:
            fmt_mr = f"Merge Request !{iid} from {source_p}/{source_branch} to {target_p}/{target_branch}"
        if href and url != "":
            return f"<a href='{url}'>{fmt_mr}</a>"
        else:
            return fmt_mr

    def format_content(self):
        shortendescr = True

        user = self.get_main_user()
        fmt_user = self.format_user(user)

        project = self.get_project()
        fmt_project = self.format_project(project)

        oas = self.content.get("object_attributes",{})

        fmt_mr = MergeFormatter.format_mr(oas)

        action =  oas.get("action", "did something unknown to")
        verb = self.get_verb_passive(action)


        description = oas.get("description", "")
        if shortendescr:
            fmt_description = description
        else:
            if description.count("\n") > 3:
                fmt_description = "\n".join(description.split("\n")[:3])
                fmt_description += "..."

        #if self.verbose and action == "open":
        if action == "open":
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
        url = oas.get("url", "")
        title = oas.get("title", "")
        fmt = f"Wiki Page <code>{title}</code>"
        if href and url != "":
            return self.format_link(url, fmt)
        else:
            return fmt

    def format_content(self):
        shortendescr = True

        user = self.get_main_user()
        fmt_user = self.format_user(user)

        project = self.get_project()
        fmt_project = self.format_project(project)

        oas = self.content.get("object_attributes",{})
        fmt_wiki = self.format_wiki_page(oas)

        action = oas.get("action", "did something unknown to")
        verb = self.get_verb_passive(action)

        return f"{fmt_user} {verb} {fmt_wiki} in {fmt_project}"



class PipelineFormatter(Formatter):
    """
    TODO: add hyperlinks
    """
    emojidict = {
            "success": "✅",
            "fail": "❌",
            "skipped": "➡️",
            "created": "⬆️",
            }

    def format_build(self, builddict):
        name = builddict.get("name", "build")
        stage = builddict.get("stage", "")
        if stage != "":
            stage = f"({stage})"
        status = builddict.get("status", "unknown status")
        if self.emojis:
            emoji = self.emojidict.get(status,"")
            if emoji != "":
                emoji = f"{emoji} "
            return f"{emoji}{name}{stage}: <code>{status}</code>"
        else:
            return f"{name}{stage}: <code>{status}</code>"

    def format_pipeline(self, oas):
        status = oas.get("status", "Unknown Status")
        stages = oas.get("stages", [])
        ref = oas.get("ref", "")
        pid = oas.get("id", "")
        source = oas.get("source")
        if self.emojis:
            statusemoji = self.emojidict.get(status,"")
        return f"Pipeline {pid} triggered by {source} exited with status {statusemoji}<code>{status}</code>"

    def format_content(self):
        #user = self.get_main_user()
        #fmt_user = self.format_user(user)

        project = self.get_project()
        fmt_project = self.format_project(project)

        oas = self.content.get("object_attributes",{})
        fmt_pipeline = self.format_pipeline(oas) 

        base = f"{fmt_pipeline} in {fmt_project}"
        if self.verbose:
            base += "\n<ul>"
            for build in self.content.get("builds", []):
                base += "\n<li>"
                base += self.format_build(build)
                base += "</li>"
            base += "\n</ul>"
            return base
        else:
            return base


class JobFormatter(Formatter):
    emojidict = {
            "success": "✅",
            "fail": "❌",
            "skipped": "➡️",
            "created": "⬆️",
            }

    def format_project(self):
        name =  self.content.get("project_name", "")
        url = self.content.get("repository", {}).get("homepage", "")
        return self.format_link(url, name)

    def format_build(self):
        name = self.content.get("build_name", "build")
        stage = self.content.get("build_stage", "")
        if stage != "":
            stage = f"({stage})"
        status = self.content.get("build_status", "unknown status")
        if self.emojis:
            emoji = self.emojidict.get(status,"")
            if emoji != "":
                emoji = f"{emoji} "
            return f"{emoji}{name}{stage}: <code>{status}</code>"
        else:
            return f"{name}{stage}: <code>{status}</code>"

    def format_content(self):
        fmt_project = self.format_project()
        fmt_build = self.format_build() 

        base = f"Job Event: {fmt_build} in {fmt_project}"
        return base


def format_event(event, content, verbose=False, emojis=True, asnotice=True):
    """
    TODO: change verbose to a verbosity level with multiple (>2) options
    returns None if event shouldn't be printed
    """
    formatters = {
            "Push Hook" : PushFormatter,
            "Tag Push Hook" : TagPushFormatter,
            "Issue Hook" : IssueFormatter,
            "Note Hook" : NoteFormatter,
            "Merge Request Hook" : MergeFormatter,
            "Wiki Page Hook" : WikiFormatter,
            "Pipeline Hook" : PipelineFormatter,
            "Job Hook" : JobFormatter,
            }

    if event in formatters:
        return formatters[event](event, content, verbose, emojis, asnotice).format()
    elif "Confidential" in event:
        return None
    return f"Unknown event received: {event}. Please poke the maintainers."
