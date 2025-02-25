from __future__ import annotations

import html
import logging
import typing
from abc import ABC, abstractmethod

from pydantic import BaseModel

if typing.TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)


class Sender(BaseModel):
    id: str
    login: str
    html_url: str | None = None
    avatar_url: str | None = None


class Repo(BaseModel):
    id: str
    name: str
    description: str
    html_url: str | None = None


class Commit(BaseModel):
    id: str
    message: str
    timestamp: str
    url: str
    author: Sender
    added: str
    modified: str
    removed: str


class PR(BaseModel):
    number: str
    html_url: str
    title: str
    merged: str


class Formatter(ABC):
    def __init__(self, event: str, content: dict[str, Any], config: dict) -> None:
        self.event = event
        self.content = content

        self.verbose = config.get("verbose")
        self.emojis = config.get("emojis")
        self.asnotice = config.get("notice")

    def format(self) -> str | None:
        """
        return html representation of event with formatting options
        """
        content = self._get_content()
        if not content:
            return None

        content = content.replace("\n", "<br/>")

        if self.emojis:
            return f"🐱 {content}"

        return content

    @abstractmethod
    def _get_content(self) -> str | None:
        pass

    def _format_link(self, url: str, linktext: str):
        return f"<a href='{url}'>{linktext}</a>"

    def _format_sender(self) -> str:
        sender = self._get_sender()
        if not sender:
            return "[no sender]"
        if sender.html_url:
            return self._format_link(sender.html_url, sender.login)
        return sender.login

    def _format_repo(self) -> str:
        repo = self._get_repo()
        if repo is None:
            return "[no repo]"
        if repo.html_url:
            return self._format_link(repo.html_url, repo.name)
        else:
            return repo.name

    def _format_branch(self, branchname: str) -> str:
        if self.emojis:
            return f"🌿 {branchname}"
        else:
            return f"branch {branchname}"

    def _format_tag(self, tagname: str) -> str:
        if self.emojis:
            return f"🏷 {tagname}"
        else:
            return f"tag {tagname}"

    def _format_text_block(self, text: str, cut: int = 2) -> str:
        if cut and text.count("\n") > cut:
            res = f"{'\n'.join(text.split('\n')[:cut])}\n..."
        else:
            res = text
        res = html.escape(res)
        return f"<pre><code>{res}</code></pre>"

    def _format_issue(self, issue: dict, href=True) -> str:
        if issue_id := issue.get("number"):
            issue_number = f"#{issue_id} "
        else:
            issue_number = "#?"

        title = issue.get("title", "[no title]")
        res = f"{issue_number}{title}"
        if href and (url := issue.get("html_url")):
            return self._format_link(url, res)
        else:
            return res

    def _format_pr_title(self, pr: PR, href=True) -> str:
        res = ""
        if pr.number:
            res += f"# {pr.number} "
        res += pr.title
        if pr.html_url and href:
            return self._format_link(pr.html_url, res)
        else:
            return res

    # content extraction
    def _get_sender(self) -> Sender | None:
        if sender_raw := self.content.get("sender"):
            return Sender(**sender_raw)

        return None

    def _get_repo(self) -> Repo | None:
        if repo_raw := self.content.get("repository"):
            return Repo(**repo_raw)

        return None


class BranchTagCreateFormatter(Formatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#create
    """
    def _get_content(self) -> str | None:
        fmt_repo = self._format_repo()
        fmt_sender = self._format_sender()

        ref = self.content.get("ref", "")
        ref_type = self.content.get("ref_type", "something")

        fmt_tn = f"{ref_type} {ref}" if ref_type != "branch" else self._format_branch(ref)
        fmt = f"{fmt_sender} created {fmt_tn} in {fmt_repo}"
        return fmt


class BranchTagDeleteFormatter(Formatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#delete
    """
    def _get_content(self) -> str | None:
        fmt_repo = self._format_repo()
        fmt_sender = self._format_sender()

        ref = self.content.get("ref", "")
        ref_type = self.content.get("ref_type", "something")

        fmt_tn = f"{ref_type} {ref}" if ref_type != "branch" else self._format_branch(ref)
        fmt = f"{fmt_sender} deleted {fmt_tn} in {fmt_repo}"
        return fmt


class ForkFormatter(Formatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#fork
    """
    def _format_forkee(self, href=True):
        forkee = self.content.get("forkee", {})
        name = forkee.get("full_name", "[no name]")
        if href and (url := forkee.get("html_url")):
            return self._format_link(url, name)
        else:
            return name

    def _get_content(self) -> str | None:
        fmt_repo = self._format_repo()
        fmt_sender = self._format_sender()
        fmt = f"{fmt_sender} forked {fmt_repo}: {self._format_forkee()}"
        return fmt


class IssueCommentFormatter(Formatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#issue_comment
    """
    def _get_content(self) -> str | None:
        fmt_repo = self._format_repo()
        fmt_sender = self._format_sender()

        action = self.content.get("action", "did something unknown to")

        ret: str | None = None
        fmt_issue = self._format_issue(self.content["issue"])

        try:
            fmt_body = self._format_text_block(self.content["comment"]["body"])
        except KeyError:
            fmt_body = None

        if action in {"created", "edited"}:
            if action == "created":
                ret = f"{fmt_sender} commented issue {fmt_issue} in {fmt_repo}"

                if self.verbose:
                    ret += f":\n{fmt_body}\n"

            elif action == "edited" and self.verbose:
                ret = f"{fmt_sender} edited issue comment {fmt_issue} in {fmt_repo}"

                fmt_body = self._format_text_block(self.content["comment"]["body"])
                changes = self.content["changes"]
                fmt_old_body = self._format_text_block(changes["body"]["from"])
                ret = (f"{fmt_sender} changed comment on issue {fmt_issue} of "
                       f"{fmt_repo}:\nfrom:\n{fmt_old_body}\nto:\n{fmt_body}\n")

            else:
                raise Exception("wtf")

        elif self.verbose:
            ret = f"{fmt_sender} {action} comment on issue {fmt_issue} in {fmt_repo}"
            if fmt_body:
                ret += ":\n{fmt_body}\n"

        return ret


class IssueFormatter(Formatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#issues
    """
    def _get_content(self) -> str | None:
        fmt_repo = self._format_repo()
        fmt_sender = self._format_sender()

        action = self.content.get("action", "did something unknown to")

        if action not in {"opened", "reopened", "closed", "pinned", "unpinned"} and not self.verbose:
            return None

        new = "new issue" if action == "opened" else "issue"
        issue = self.content["issue"]
        fmt_issue = self._format_issue(issue)

        fmt = f"{fmt_sender} {action} {new} {fmt_issue} in {fmt_repo}"

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


class MemberFormatter(Formatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#member
    """
    def _get_content(self) -> str | None:
        fmt_repo = self._format_repo()
        fmt_sender = self._format_sender()
        action = self.content.get("action", "done something to")
        if not (self.verbose or action in {"added", "removed"}):
            return None

        fmt = f"{fmt_repo}: Member {fmt_sender} has been {action}"
        return fmt


class MetaFormatter(Formatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#meta
    """
    def _get_content(self) -> str | None:
        fmt_repo = self._format_repo()
        fmt_sender = self._format_sender()
        action = self.content.get("action", "changed")
        fmt = f"{fmt_sender} {action} a webhook on {fmt_repo}"
        return fmt


class PingFormatter(Formatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#ping
    """
    def _get_content(self) -> str | None:
        fmt_repo = self._format_repo()
        fmt_sender = self._format_sender()
        fmt = f"{fmt_sender} added a webhook to {fmt_repo}"
        return fmt


class PublicFormatter(Formatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#public
    """
    def _get_content(self) -> str | None:
        fmt_repo = self._format_repo()
        fmt_sender = self._format_sender()
        fmt = f"{fmt_sender} published repo: {fmt_repo}"
        return fmt


class PullRequestFormatter(Formatter):
    """
    https://docs.github.com/en/webhooks/webhook-events-and-payloads#pull_request
    """

    emojidict = {
        "success": "✅",
        "fail": "❌",
    }

    def _get_content(self) -> str | None:
        fmt_repo = self._format_repo()
        fmt_sender = self._format_sender()
        action = self.content.get("action", "touched")

        pr = PR(**self.content["pull_request"])
        pr_t = self._format_pr_title(pr)

        match action:
            case "opened" | "reopened":
                fmt = f"{fmt_sender} {action} pull request {pr_t} in {fmt_repo}"

                return fmt

            case "closed":
                if pr.merged:
                    fmt = f"{fmt_sender} merged pull request {pr_t} in {fmt_repo}"
                    if self.emojis:
                        fmt += self.emojidict["success"]

                else:
                    fmt = f"{fmt_sender} closed pull request {pr_t} in {fmt_repo}"
                    if self.emojis:
                        fmt += self.emojidict["fail"]

                return fmt

            case "synchronize":
                if self.verbose:
                    return f"{fmt_sender} {action} pushed to pull request {pr_t} in {fmt_repo}"

            case _:
                if self.verbose:
                    return f"{fmt_sender} {action} pull request {pr_t} in {fmt_repo}"

        return None


class PullRequestReviewFormatter(Formatter):
    def _get_content(self) -> str | None:
        action = self.content.get("action", "touched")

        fmt_repo = self._format_repo()
        fmt_sender = self._format_sender()
        pr = PR(**self.content["pull_request"])
        pr_t = self._format_pr_title(pr)

        match self.event:
            case "pull_request_review":
                match action:
                    case "submitted":
                        review_link = self._format_link(self.content["review"]["html_url"], 'reviewed')
                        return f"{fmt_sender} {review_link} pull request {pr_t} in {fmt_repo}"
                    case _:  # edited, dismissed, ...
                        if self.verbose:
                            return f"{fmt_sender} {action} pull request {pr_t} in {fmt_repo}"

            case "pull_request_review_comment":
                if self.verbose:
                    comment = self._format_link(self.content['comment']['html_url'], 'review comment')
                    return (f"{fmt_sender} {action} {comment} in pull request {pr_t} in {fmt_repo}")

            case "pull_request_review_thread":
                if self.verbose:
                    comment = self._format_link(self.content['thread']['comments'][0]['html_url'], 'review thread')
                    return (f"{fmt_sender} {action} {comment} in pull request {pr_t} in {fmt_repo}")

            case _:
                raise NotImplementedError()

        return None


class PushFormatter(Formatter):
    def _format_commit(self, commit: Commit, href=True, branch=False) -> str:
        message = commit.message.split("\n")[0]
        if href and commit.url != "":
            fmt = f"{message}({self._format_link(commit.url,commit.id[:7])})"
        else:
            fmt = f"{message}({commit.id[0:7]})"

        if branch:
            fmt = "⇨ " + fmt
        return fmt

    def _format_commits(self, max_commits: int = 3):
        commits_raw = self.content.get("commits", [])

        cut = False
        if max_commits:
            cut = len(commits_raw) > max_commits
            commits_raw = commits_raw[-max_commits:]

        cut_fmt = "<li>... more</li>" if cut else ""

        commits = []
        for commit in commits_raw:
            commits.append(Commit(**commit))

        if commits:
            commits.reverse()

            commits_fmt = "".join(
                f"<li>{self._format_commit(commit, branch=(i==0))}</li>"
                for (i, commit) in enumerate(commits)
            )
            return f"<ul>{cut_fmt}{commits_fmt}</ul>"
        else:
            return "no commits"

    def _get_ref(self) -> str:
        ref = self.content["ref"]
        if ref.startswith("refs/heads/"):
            return self._format_branch(ref.lstrip("refs/heads/"))
        elif ref.startswith("refs/tags/"):
            return self._format_tag(ref.lstrip("refs/tags/"))
        else:
            return ref

    def _get_content(self) -> str | None:
        fmt_repo = self._format_repo()
        fmt_sender = self._format_sender()
        fmt_ref = self._get_ref()

        fmt_push = self._format_link(self.content["compare"], "pushed")
        fmt = f"{fmt_sender} {fmt_push} {fmt_ref} to {fmt_repo}"
        if self.verbose:
            fmt += self._format_commits()
        return fmt


class StarFormatter(Formatter):
    def _get_content(self) -> str | None:
        fmt_repo = self._format_repo()
        fmt_sender = self._format_sender()
        action = self.content.get("action", "did something related to")
        fmt = f"{fmt_sender} {action} a star for {fmt_repo}"
        return fmt


class WatchFormatter(Formatter):
    def _get_content(self) -> str | None:
        fmt_repo = self._format_repo()
        fmt_sender = self._format_sender()
        action = self.content.get("action", "did something related to")
        fmt = f"{fmt_sender} {action} watching {fmt_repo}"
        return fmt


def format_event(event, content, config):
    """
    returns None if event shouldn't be printed
    """
    # https://docs.github.com/en/developers/webhooks-and-events/webhook-events-and-payloads
    formatters = {
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

    # TODO: change verbose to a verbosity level with multiple (>2) options
    # TODO: define options here, and propagate up to the github plugin config
    if event in formatters:
        return formatters[event](event, content, config).format()

    elif "Confidential" in event:
        return None

    if config.get("verbose"):
        return f"Unknown event received: {event}. Please poke the maintainers."

    return None
