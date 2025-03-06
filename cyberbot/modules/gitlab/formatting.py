from __future__ import annotations

import textwrap
import typing

from pydantic import BaseModel

from ..util.git_formatter import PR as BasePR
from ..util.git_formatter import Commit as BaseCommit
from ..util.git_formatter import GitEventFormatter, GitFormatter
from ..util.git_formatter import Ref as BaseRef
from ..util.git_formatter import Repo as BaseRepo
from ..util.git_formatter import User as BaseUser
from ..util.git_formatter import WorkItem as BaseWorkItem

if typing.TYPE_CHECKING:
    from typing import Any


class User(BaseModel):
    id: int
    name: str
    username: str
    email: str
    avatar_url: str

    def to_base(self) -> BaseUser:
        return BaseUser(name=self.name, login=self.username, url=None)


class UserFlat(BaseModel):
    """
    some events (e.g. push) have the userinfo in the toplevel json object.
    """
    user_id: int
    user_name: str
    user_username: str
    user_email: str
    user_avatar: str

    def to_base(self) -> BaseUser:
        return BaseUser(name=self.user_name, login=self.user_username, url=None)

    def to_user(self) -> User:
        return User(id=self.user_id, name=self.user_name, username=self.user_username,
                    email=self.user_email, avatar_url=self.user_avatar)


class Project(BaseModel):  # aka Repository
    id: int
    name: str
    description: str
    web_url: str

    def to_base(self) -> BaseRepo:
        return BaseRepo(name=self.name, url=self.web_url)


class MergeRequest(BaseModel):
    iid: int
    title: str
    state: str
    url: str | None
    work_in_progress: bool
    draft: bool

    def to_base(self) -> BasePR:
        return BasePR(number=self.iid, title=self.title, url=self.url, state=self.state)


class WorkItem(BaseModel):
    iid: int
    title: str
    description: str
    url: str

    def to_base(self) -> BaseWorkItem:
        return BaseWorkItem(number=self.iid, title=self.title, url=self.url)


class CodeSnippet(BaseModel):
    title: str
    url: str
    file_name: str


class CommitUser(BaseModel):
    name: str
    email: str

    def to_base(self) -> BaseUser:
        return BaseUser(name=self.name, login=None, url=None)


class Commit(BaseModel):
    id: int
    message: str
    title: str
    timestamp: str
    url: str
    author: CommitUser
    added: list[str]
    modified: list[str]
    removed: list[str]

    def to_base(self) -> BaseCommit:
        return BaseCommit(author=self.author.to_base(), id=self.id, title=self.title, url=self.url)


class Pipeline(BaseModel):
    name: str
    source: str
    url: str
    status: str
    stages: list[str]


class Job(BaseModel):
    name: str
    status: str
    stage: str | None


class Vulnerability(BaseModel):
    url: str
    title: str
    severity: str
    state: str


class GitLabEventFormatter(GitEventFormatter):
    def __init__(self, event: str, content: dict[str, Any], config: dict[str, bool]) -> None:
        self.event = event
        self.content = content

        self.verbose = config["verbose"]

        super().__init__(
            main_emoji="🦊",
            emojis=config["emoji"],
        )

    # content extraction
    def _get_user(self) -> User:
        if sender_raw := self.content.get("user"):
            return User(**sender_raw)
        elif self.content.get("user_username"):
            return UserFlat(**self.content).to_user()

        raise ValueError("'user'/'user_username' missing from content")

    def _get_project(self) -> Project:
        if project_raw := self.content.get("project"):
            return Project(**project_raw)

        raise ValueError("'project' missing from content")

    def _fmt_repo_action(self, action: str) -> str:
        return self._format_repo_action(
            repo=self._get_project().to_base(),
            user=self._get_user().to_base(),
            action=action,
        )

    def _fmt_repo_event(self, event: str) -> str:
        return self._format_repo_event(
            repo=self._get_project().to_base(),
            event=event,
        )

    def _get_verb_passive(self, action: str) -> str:
        if action.endswith("ed"):
            return action
        elif action.endswith("e"):
            return f"{action}d"
        else:
            return f"{action}ed"


class PushFormatter(GitLabEventFormatter):
    """
    https://docs.gitlab.com/user/project/integrations/webhook_events/#push-events
    """
    def _fmt_commits(self, max_commits: int = 3):
        commits_raw = self.content.get("commits", [])

        commits: list[BaseCommit] = []
        for commit in commits_raw:
            commits.append(Commit(**commit).to_base())

        return self._format_commits(commits, max_commits=max_commits)

    def _get_content(self) -> str | None:
        ref = self.content["ref"]
        fmt_ref = self._format_ref(BaseRef(ref=ref, ref_type="branch"))

        # there seems to be no before-after comparison web url
        fmt = self._fmt_repo_action(f"pushed {fmt_ref}")

        if self.verbose:
            fmt += self._fmt_commits()
        return fmt


class TagPushFormatter(GitLabEventFormatter):
    """
    https://docs.gitlab.com/user/project/integrations/webhook_events/#tag-events
    """
    def _get_action(self):
        zeroes = "0" * 40
        after = self.content["after"]
        before = self.content["before"]
        if after == zeroes:
            return "deleted"
        elif before == zeroes:
            return "pushed new"
        else:
            return "changed"

    def _get_content(self) -> str | None:
        tag = BaseRef(ref=self.content["ref"], ref_type="tag")
        fmt_tag = self._format_ref(tag)
        verb = self._get_action()

        return self._fmt_repo_action(f"{verb} {fmt_tag}")


class WorkItemFormatter(GitLabEventFormatter):
    """
    https://docs.gitlab.com/user/project/integrations/webhook_events/#work-item-events
    """
    def _get_content(self) -> str | None:
        oas = self.content["object_attributes"]
        objtype = oas["type"].lower()
        action = oas["action"]

        item = f"new {objtype}" if action == "open" else objtype
        verb = self._get_verb_passive(action)
        fmt_work_item = self._format_workitem_title(WorkItem(**oas).to_base())
        fmt = self._fmt_repo_action(f"{verb} {item} {fmt_work_item}")

        if not self.verbose:
            return fmt

        match action:
            case "opened":
                description = oas.get("description", "").strip()
                if description:
                    fmt += f":\n{self._format_text_block(description)}"
            case _:
                pass

        return fmt


class CommentFormatter(GitLabEventFormatter):
    """
    https://docs.gitlab.com/ee/user/project/integrations/webhooks.html#comment-events
    four types of comments: commit, merge request, issue, code snippet
    """

    def _format_target(self, oas) -> str:
        comment_type = oas["noteable_type"]
        comment_url = oas["url"]

        match comment_type:
            case "Issue":
                issue = WorkItem(**self.content["issue"])
                item = self._format_workitem_nr(issue.to_base(), href=False)
                return self._format_link(comment_url, f"issue {item}")

            case "MergeRequest":
                mr = MergeRequest(**self.content["merge_request"])
                item = self._format_workitem_nr(mr.to_base(), href=False)
                return self._format_link(comment_url, f"merge request {item}")

            case "Snippet":
                snip = CodeSnippet(**self.content["snippet"])
                return self._format_link(
                    snip.url, f"snippet {textwrap.shorten(snip.title, width=60)} ({snip.file_name})"
                )

            case "Commit":
                commit = Commit(**self.content["commit"])
                cmsg = commit.message[:commit.message.index('\n')]
                return self._format_link(
                    commit.url, f"commit {textwrap.shorten(cmsg, width=60)}"
                )

            case _:
                return f"{comment_type.lower()}"

    def _get_content(self) -> str | None:
        oas = self.content["object_attributes"]

        fmt_target = self._format_target(oas)

        ret = self._fmt_repo_action(f"commented on {fmt_target}")

        if self.verbose:
            fmt_note = self._format_text_block(oas["note"])
            return f":\n{fmt_note}"

        return ret


class MergeFormatter(GitLabEventFormatter):
    def _get_content(self) -> str | None:

        oas = self.content["object_attributes"]

        action = oas["action"]
        verb = self._get_verb_passive(action)

        mr = MergeRequest(**oas)

        if action == "open":
            fmt_mr = self._format_pr_title(mr.to_base())
            return self._fmt_repo_action(f"{verb} merge request {fmt_mr}")

        fmt_mrid = self._format_workitem_nr(mr.to_base())
        fmt_action = self._fmt_repo_action(f"{verb} merge request {fmt_mrid}")

        match action:
            case "open":
                raise Exception("handled earlier")
            case "reopen":
                return fmt_action
            case "merge":
                return self._format_state(fmt_action, state="success")
            case "close":
                return self._format_state(fmt_action, state="fail")
            case _:
                # "update" | "approve" | "approval" | "unapproved" | "unapproval", ...
                if self.verbose:
                    return fmt_action

        return None


class WikiFormatter(GitLabEventFormatter):
    def _fmt_wiki_page(self, oas: dict) -> str:
        title = oas["title"]

        fmt = f"wiki page <code>{textwrap.shorten(title, width=50)}</code>"
        if url := oas.get("url"):
            return self._format_link(url, fmt)
        else:
            return fmt

    def _get_content(self) -> str | None:
        oas = self.content["object_attributes"]

        fmt_wiki = self._fmt_wiki_page(oas)

        action = oas["action"]
        verb = self._get_verb_passive(action)

        return self._fmt_repo_action(f"{verb} {fmt_wiki}")


class BuildEventFormatter(GitLabEventFormatter):
    """
    common stuff for PipelineFormatter and JobFormatter
    """

    def _format_job(self, job: Job):
        if stage := job.stage:
            stage = f"({stage})"
        else:
            stage = ""

        return self._format_state(f"{job.name}{stage}: <code>{job.status}</code>", state=job.status)


class PipelineFormatter(BuildEventFormatter):
    """
    https://docs.gitlab.com/user/project/integrations/webhook_events/#pipeline-events
    """

    def _format_pipeline(self, pipeline: Pipeline):
        fmt_pl = self._format_link(pipeline.url, f"pipeline {textwrap.shorten(pipeline.name, 40)}")
        fmt = f"{fmt_pl}: <code>{pipeline.status}</code>"
        return self._format_state(fmt, state=pipeline.status)

    def _get_content(self) -> str | None:
        pipeline = Pipeline(**self.content["object_attributes"])

        if pipeline.status not in {"fail", "success"} and not self.verbose:
            return None

        fmt_pipeline = self._format_pipeline(pipeline)
        fmt = self._fmt_repo_event(fmt_pipeline)

        if not self.verbose:
            return fmt

        builds: list[str] = list()

        for job in self.content.get("builds", []):
            builds.append(f"<li>{self._format_job(Job(**job))}</li>")

        if builds:
            fmt += f":\\n<ul>{'\\n'.join(builds)}</ul>"

        return fmt


class JobFormatter(BuildEventFormatter):
    """
    https://docs.gitlab.com/user/project/integrations/webhook_events/#job-events
    """
    def _get_content(self) -> str | None:
        job = Job(
            name=self.content["build_name"],
            stage=self.content["build_stage"],
            status=self.content["build_status"],
        )
        fmt_job = self._format_job(job)

        return self._fmt_repo_event(f"job {fmt_job}")


class VulnerabilityFormatter(GitLabEventFormatter):
    """
    https://docs.gitlab.com/user/project/integrations/webhook_events/#vulnerability-events
    """
    def _get_content(self) -> str | None:
        vuln = Vulnerability(**self.content["object_attributes"])

        fmt_title = f"{textwrap.shorten(vuln.title, 80)!r}"
        fmt_link = self._format_link(vuln.url, f"vulnerability {fmt_title}")
        fmt_vuln = self._format_state(f"{vuln.severity} {fmt_link}: <code>{vuln.state}</code>", vuln.state)
        return self._fmt_repo_event(fmt_vuln)


class GitLabFormatter(GitFormatter):
    def format(
        self,
        event: str,
        content: Any,
        config: dict[str, bool]
    ) -> str | None:
        """
        returns None if event shouldn't be printed
        """

        # https://docs.gitlab.com/user/project/integrations/webhook_events/
        formatters: dict[str, type[GitLabEventFormatter]] = {
            "Push Hook": PushFormatter,
            "Tag Push Hook": TagPushFormatter,
            "Issue Hook": WorkItemFormatter,
            "Note Hook": CommentFormatter,
            "Merge Request Hook": MergeFormatter,
            "Wiki Page Hook": WikiFormatter,
            "Pipeline Hook": PipelineFormatter,
            "Job Hook": JobFormatter,
            "Vulnerability Hook": VulnerabilityFormatter,
        }

        if formatter := formatters.get(event):
            return formatter(event, content, config).format()

        elif "Confidential" in event:
            return None

        elif config["verbose"]:
            return f"GitLab event received: {event!r}."

        return None

    def get_config(self) -> dict[str, bool]:
        return {
            "verbose": False,
            "emoji": True,
            "notice": True,
        }
