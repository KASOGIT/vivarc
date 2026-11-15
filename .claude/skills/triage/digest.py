#!/usr/bin/env python3
"""Print what changed on open PRs and issues since the maintainer last spoke on each.

NEW: the maintainer never spoke. UPDATED: someone else commented or pushed after the maintainer's last word.
OWNER_LAST: the maintainer spoke last (read that comment: the ball can be on either side).
`idle=Nd` is days since the last event of any kind. Issues closed by an open PR are folded into that PR.
Args: optional states to show, e.g. `digest.py NEW UPDATED`."""
import json
import subprocess
import sys
from datetime import datetime, timezone

REPO = "KASOGIT/vivarc"
OWNER = "KASOGIT"

QUERY = """
query($owner:String!, $name:String!) {
  repository(owner:$owner, name:$name) {
    pullRequests(states:OPEN, first:50, orderBy:{field:UPDATED_AT, direction:DESC}) { pageInfo{ hasNextPage } nodes {
      number title author{login} createdAt isDraft mergeable reviewDecision additions deletions changedFiles
      headRefName isCrossRepository
      commits(last:1){ nodes{ commit{ committedDate statusCheckRollup{ state } } } }
      allCommits: commits(last:100){ nodes{ commit{ committedDate messageHeadline author{ user{ login } } } } }
      comments(last:100){ nodes{ author{login} createdAt body } }
      reviews(last:50){ nodes{ author{login} createdAt state body } }
      closingIssuesReferences(first:10){ nodes{ number } }
    } }
    issues(states:OPEN, first:100, orderBy:{field:UPDATED_AT, direction:DESC}) { pageInfo{ hasNextPage } nodes {
      number title author{login} createdAt labels(first:10){ nodes{ name } }
      comments(last:100){ nodes{ author{login} createdAt body } }
    } }
  }
}
"""


def gh_graphql():
    owner, name = REPO.split("/")
    out = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={QUERY}", "-F", f"owner={owner}", "-F", f"name={name}"],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)["data"]["repository"]


def login(node):
    return (node.get("author") or {}).get("login", "ghost")


def status(events, created, author):
    """events: list of (time, who, kind, text). Returns state and the events after the owner's last word."""
    owner_times = [t for t, who, _, _ in events if who == OWNER]
    if author == OWNER:
        last_owner = max(owner_times + [created])
    elif not owner_times:
        return "NEW", events
    else:
        last_owner = max(owner_times)
    after = [e for e in events if e[0] > last_owner and e[1] != OWNER]
    return ("UPDATED" if after else "OWNER_LAST"), after


def idle(events, created):
    last = max([e[0] for e in events] + [created])
    then = datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then).days


def last_word(events):
    said = [e for e in events if e[1] == OWNER and e[2] != "commit" and e[3]]
    return said[-1] if said else None


def short(text, n=160):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def main():
    repo = gh_graphql()
    rows = []
    covered = {}
    for pr in repo["pullRequests"]["nodes"]:
        for i in pr["closingIssuesReferences"]["nodes"]:
            covered[i["number"]] = pr["number"]
    for pr in repo["pullRequests"]["nodes"]:
        author = login(pr)
        events = [(c["createdAt"], login(c), "comment", c["body"]) for c in pr["comments"]["nodes"]]
        events += [(r["createdAt"], login(r), f"review:{r['state']}", r["body"]) for r in pr["reviews"]["nodes"]]
        events += [(c["commit"]["committedDate"], ((c["commit"]["author"] or {}).get("user") or {}).get("login", author),
                    "commit", c["commit"]["messageHeadline"]) for c in pr["allCommits"]["nodes"]]
        events.sort()
        state, after = status(events, pr["createdAt"], author)
        last = pr["commits"]["nodes"][0]["commit"] if pr["commits"]["nodes"] else {}
        ci = (last.get("statusCheckRollup") or {}).get("state", "NONE")
        closes = ",".join(f"#{i['number']}" for i in pr["closingIssuesReferences"]["nodes"])
        rows.append((state, last_word(events), f"PR #{pr['number']} [{state}] idle={idle(events, pr['createdAt'])}d {pr['title']} (@{author}{', draft' if pr['isDraft'] else ''})\n"
                     f"   ci={ci} mergeable={pr['mergeable']} review={pr['reviewDecision']} "
                     f"+{pr['additions']}/-{pr['deletions']} files={pr['changedFiles']} closes={closes or '-'} "
                     f"fork={pr['isCrossRepository']}", after))
    for issue in repo["issues"]["nodes"]:
        if issue["number"] in covered:
            continue
        author = login(issue)
        events = sorted((c["createdAt"], login(c), "comment", c["body"]) for c in issue["comments"]["nodes"])
        state, after = status(events, issue["createdAt"], author)
        labels = ",".join(l["name"] for l in issue["labels"]["nodes"])
        rows.append((state, last_word(events), f"Issue #{issue['number']} [{state}] idle={idle(events, issue['createdAt'])}d {issue['title']} (@{author}) labels={labels or '-'} "
                     f"comments={len(events)}", after))

    order = {"NEW": 0, "UPDATED": 1, "OWNER_LAST": 2}
    only = set(sys.argv[1:]) or set(order)
    for state, word, head, after in sorted(rows, key=lambda r: order[r[0]]):
        if state not in only:
            continue
        print(head)
        if state == "OWNER_LAST" and word:
            print(f"   last owner word {word[0][:10]}: {short(word[3], 300)}")
        for t, who, kind, text in after[-8:]:
            print(f"   {t[:16]} @{who} {kind}: {short(text)}")
    for kind in ("pullRequests", "issues"):
        if repo[kind]["pageInfo"]["hasNextPage"]:
            print(f"WARNING: more open {kind} than fetched, raise the limit in digest.py")
    counts = {s: sum(1 for r in rows if r[0] == s) for s in order}
    print(f"\n{counts}")
    if covered:
        print("issues folded into their PR: " + ", ".join(f"#{i}->PR #{p}" for i, p in sorted(covered.items())))


if __name__ == "__main__":
    main()
