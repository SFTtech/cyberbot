from __future__ import annotations

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
    name: str
    username: str | None = None
    html_url: str | None = None
    avatar_url: str | None = None

    def to_base(self) -> BaseUser:
        return BaseUser(name=self.name, login=self.username, url=self.html_url)


class Repo(BaseModel):
    name: str
    description: str
    html_url: str | None = None

    def to_base(self) -> BaseRepo:
        return BaseRepo(name=self.name, url=self.html_url)


class Issue(BaseModel):
    number: int
    title: str
    html_url: str | None = None

    def to_base(self) -> BaseWorkItem:
        return BaseWorkItem(number=self.number, title=self.title, url=self.html_url)


class PR(BaseModel):
    number: int
    html_url: str
    title: str
    state: str  # open, closed
    merged: bool

    def to_base(self) -> BasePR:
        return BasePR(number=self.number, title=self.title, state=self.state, url=self.html_url)


class Commit(BaseModel):
    id: str
    message: str
    timestamp: str
    author: User | None
    committer: User
    added: list[str]
    modified: list[str]
    removed: list[str]
    url: str | None = None

    def to_base(self) -> BaseCommit:
        return BaseCommit(id=self.id, title=self.message[:self.message.index('\n')],
                          author=(self.author or self.committer).to_base(), url=self.url)


class Ref(BaseModel):
    ref: str
    ref_type: str  # branch, tag

    def to_base(self) -> BaseRef:
        return BaseRef(ref=self.ref, ref_type=self.ref_type)


class GitHubEventFormatter(GitEventFormatter):
    def __init__(self, event: str, content: dict[str, Any], config: dict[str, bool]) -> None:
        self.event = event
        self.content = content

        self.verbose = config["verbose"]

        super().__init__(
            main_emoji="🐱",
            emojis=config["emoji"],
        )

    # content extraction
    def _get_sender(self) -> User:
        if sender_raw := self.content.get("sender"):
            return User(**sender_raw)

        raise ValueError("'sender' missing in content")

    def _get_repo(self) -> Repo:
        if repo_raw := self.content.get("repository"):
            return Repo(**repo_raw)

        raise ValueError("'repository' missing in content")

    def _get_issue(self) -> Issue:
        if issue_raw := self.content.get("issue"):
            return Issue(**issue_raw)
        raise ValueError("'issue' missing in content")

    def _get_pr(self) -> PR:
        if pr_raw := self.content.get("pull_request"):
            return PR(**pr_raw)
        raise ValueError("'pull_request' missing in content")

    def _fmt_repo_action(self, action: str) -> str:
        return self._format_repo_action(
            repo=self._get_repo().to_base(),
            user=self._get_sender().to_base(),
            action=action,
        )

    def _fmt_ref(self):
        ref = Ref(ref=self.content["ref"], ref_type=self.content["ref_type"])
        base_ref = ref.to_base()
        return self._format_ref(base_ref)


class BranchTagCreateFormatter(GitHubEventFormatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#create
    """
    def _get_content(self) -> str | None:
        fmt_ref = self._fmt_ref()
        return self._fmt_repo_action(f"created {fmt_ref}")


class BranchTagDeleteFormatter(GitHubEventFormatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#delete
    """
    def _get_content(self) -> str | None:
        fmt_ref = self._fmt_ref()
        return self._fmt_repo_action(f"deleted {fmt_ref}")


class ForkFormatter(GitHubEventFormatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#fork
    """
    def _format_forkee(self, href=True):
        forkee = self.content["forkee"]
        name = forkee["full_name"]
        if href and (url := forkee.get("html_url")):
            return self._format_link(url, name)
        return name

    def _get_content(self) -> str | None:
        return self._fmt_repo_action(f"forked repo to {self._format_forkee()}")


class IssueCommentFormatter(GitHubEventFormatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#issue_comment
    """
    def _get_content(self) -> str | None:
        action = self.content.get("action", "did something unknown to")

        ret: str | None = None
        item_id = self._format_workitem_nr(self._get_issue().to_base())

        try:
            fmt_body = self._format_text_block(self.content["comment"]["body"])
        except KeyError:
            fmt_body = None

        what = "pull request" if "pull_request" in self.content["issue"] else "issue"

        if action in {"created", "edited"}:
            if action == "created":
                ret = self._fmt_repo_action(f"commented {what} {item_id}")

                if self.verbose:
                    ret += f":\n{fmt_body}\n"

            elif action == "edited" and self.verbose:
                changes = self.content["changes"]
                fmt_old_body = self._format_text_block(changes["body"]["from"])

                ret = (self._fmt_repo_action(f"edited {what} comment {item_id}:") +
                       f":\nfrom:\n{fmt_old_body}\nto:\n{fmt_body}\n")

            else:
                raise Exception("wtf")

        elif self.verbose:
            ret = self._fmt_repo_action(f"{action} comment on {what} {item_id}")
            if fmt_body:
                ret += ":\n{fmt_body}\n"

        return ret


class IssueFormatter(GitHubEventFormatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#issues
    """
    def _get_content(self) -> str | None:
        action = self.content.get("action", "did something unknown to")

        if action not in {"opened", "reopened", "closed", "pinned", "unpinned"} and not self.verbose:
            return None

        new = "new issue" if action == "opened" else "issue"
        issue = self.content["issue"]
        fmt_issue = self._format_workitem_title(Issue(**issue).to_base())

        fmt = self._fmt_repo_action(f"{action} {new} {fmt_issue}")

        if not self.verbose:
            return fmt

        match action:
            case "opened":
                description = self.content.get("description", "").strip()
                if description:
                    fmt += f":\n{self._format_text_block(description)}"
            case _:
                pass

        return fmt


class MemberFormatter(GitHubEventFormatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#member
    """
    def _get_content(self) -> str | None:
        action = self.content.get("action", "done something to")
        if not (self.verbose or action in {"added", "removed"}):
            return None

        if member_raw := self.content.get("member"):
            member = self._format_user(User(**member_raw).to_base())
            return self._fmt_repo_action(f"{action} {member} as member")
        else:
            return self._fmt_repo_action(f"{action} a member")


class MetaFormatter(GitHubEventFormatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#meta
    """
    def _get_content(self) -> str | None:
        action = self.content.get("action", "changed")
        return self._fmt_repo_action(f"{action} a webhook")


class PingFormatter(GitHubEventFormatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#ping
    """
    def _get_content(self) -> str | None:
        return self._fmt_repo_action("added a webhook")


class PublicFormatter(GitHubEventFormatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#public
    """
    def _get_content(self) -> str | None:
        return self._fmt_repo_action("published repo")


class PullRequestFormatter(GitHubEventFormatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#pull_request
    """

    def _get_content(self) -> str | None:
        action = self.content.get("action", "touched")

        pr = self._get_pr()
        prb = pr.to_base()
        pr_t = self._format_pr_title(prb)

        fmt_action = self._fmt_repo_action(f"{action} pull request {pr_t}")

        match action:
            case "opened" | "reopened":
                return fmt_action

            case "closed":
                if pr.merged:
                    fmt = self._fmt_repo_action(f"merged pull request {pr_t}")
                    return self._format_state(fmt, state='success')

                else:
                    return self._format_state(fmt_action, state='fail')

            case "synchronize":
                if self.verbose:
                    prnr = self._format_workitem_nr(prb)
                    return self._fmt_repo_action(f"pushed to {prnr}")

            case _:
                if self.verbose:
                    return fmt_action

        return None


class PullRequestReviewFormatter(GitHubEventFormatter):
    def _get_content(self) -> str | None:
        action = self.content.get("action", "touched")

        pr = self._get_pr().to_base()
        fmt_pr = self._format_workitem_nr(pr)

        match self.event:
            case "pull_request_review":
                match action:
                    case "submitted":
                        review_link = self._format_link(self.content["review"]["html_url"], 'reviewed')
                        return self._fmt_repo_action(f"{review_link} pull request {fmt_pr}")

                    case _:  # edited, dismissed, ...
                        if self.verbose:
                            return self._fmt_repo_action(f"{action} pull request {fmt_pr}")

            case "pull_request_review_comment":
                if self.verbose:
                    comment = self._format_link(self.content['comment']['html_url'], 'review comment')
                    return self._fmt_repo_action(f"{action} {comment} in pull request {fmt_pr}")

            case "pull_request_review_thread":
                if self.verbose:
                    thread = self._format_link(self.content['thread']['comments'][0]['html_url'], 'review thread')
                    return self._fmt_repo_action(f"{action} {thread} in pull request {fmt_pr}")

            case _:
                raise NotImplementedError()

        return None


class PushFormatter(GitHubEventFormatter):
    def _fmt_commits(self, max_commits: int = 3):
        commits_raw = self.content.get("commits", [])

        commits: list[BaseCommit] = []
        for commit in commits_raw:
            commits.append(Commit(**commit).to_base())

        return self._format_commits(commits, max_commits=max_commits)

    def _get_content(self) -> str | None:
        fmt_ref = self._fmt_ref()

        fmt_push = self._format_link(self.content["compare"], "pushed")
        fmt = self._fmt_repo_action(f"{fmt_push} {fmt_ref}")

        if self.verbose:
            fmt += self._fmt_commits()
        return fmt


class StarFormatter(GitHubEventFormatter):
    def _get_content(self) -> str | None:
        action = self.content.get("action", "did something related to")
        return self._fmt_repo_action(f"{action} a star")


class WatchFormatter(GitHubEventFormatter):
    def _get_content(self) -> str | None:
        action = self.content.get("action", "did something related to")
        match action:
            case "started":
                return self._fmt_repo_action("is now watching repo")
            case _:
                return self._fmt_repo_action(f"{action} watching")


class GitHubFormatter(GitFormatter):
    def format(
        self,
        event: str,
        content: Any,
        config: dict[str, bool]
    ) -> str | None:
        """
        returns None if event shouldn't be printed
        """
        # https://docs.github.com/en/developers/webhooks-and-events/webhook-events-and-payloads
        formatters: dict[str, type[GitHubEventFormatter]] = {
            "create": BranchTagCreateFormatter,
            "delete": BranchTagDeleteFormatter,
            "fork": ForkFormatter,
            "issue_comment": IssueCommentFormatter,
            "issues": IssueFormatter,
            "member": MemberFormatter,
            "meta": MetaFormatter,
            "ping": PingFormatter,
            "public": PublicFormatter,
            "pull_request": PullRequestFormatter,
            "pull_request_review": PullRequestReviewFormatter,
            "pull_request_review_comment": PullRequestReviewFormatter,
            "pull_request_review_thread": PullRequestReviewFormatter,
            "push": PushFormatter,
            "star": StarFormatter,
            "watch": WatchFormatter,
        }

        if formatter := formatters.get(event):
            return formatter(event, content, config).format()

        elif config["verbose"]:
            return f"GitHub event received: {event!r}."

        return None

    def get_config(self) -> dict[str, bool]:
        return {
            "verbose": False,
            "emoji": True,
            "notice": True,
        }
