"""Keep Buffer's queue loaded with the next Reels at exact 7am / 5pm Central slots.

Buffer does the timing; this only needs to run now and then (GitHub's cron is often hours late).
Usage: python scheduler/topup.py [--now]   (--now also posts the next Reel immediately)
"""
import json, os, re, sys, datetime, urllib.request
from zoneinfo import ZoneInfo

API = "https://api.buffer.com"
ORG_ID = "6adfe7f4730bcfe1e394b79c"
CHANNEL_ID = "6adffc3a2f1f5ed648e313df"
TIKTOK_ID = "6ae289f42f1f5ed64805d6b6"  # one TikTok a day, alongside the 5pm Instagram post
EXPECTED_NAME = "tailoringtraditionsclub"
BASE = "https://rogerstheboss12-coder.github.io/tailoring-traditions-assets/final/"
CT = ZoneInfo("America/Chicago")
SLOT_HOURS = (7, 17)
AHEAD = 5  # Reels to keep waiting in Buffer (free plan: 10 scheduled per channel = 5 Reels + their 5 Stories)
IG_LIMIT = 10
TOKEN = os.environ["BUFFER_TOKEN"]

def gql(query, variables=None):
    req = urllib.request.Request(API, data=json.dumps({"query": query, "variables": variables or {}}).encode(),
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.load(r)
    if out.get("errors"):
        sys.exit(f"Buffer error: {out['errors']}")
    return out["data"]

def utc_str(dt):
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def next_slot(after):
    """First 7am/5pm Central slot strictly after `after` (aware datetime)."""
    local = after.astimezone(CT)
    day = local.date()
    while True:
        for h in SLOT_HOURS:
            slot = datetime.datetime(day.year, day.month, day.day, h, tzinfo=CT)
            if slot > local + datetime.timedelta(minutes=10):
                return slot
        day += datetime.timedelta(days=1)

posts = json.load(open("posts.json"))
state = json.load(open("scheduler/state.json"))

chans = gql('query($o: OrganizationId!){ channels(input:{organizationId:$o}){ id name service } }', {"o": ORG_ID})["channels"]
chan = next((c for c in chans if c["id"] == CHANNEL_ID), None)
if not chan or chan["name"] != EXPECTED_NAME or chan["service"] != "instagram":
    sys.exit(f"Refusing to post: channel check failed ({chan})")

def create(post, due=None):
    video = BASE + post["file"].rsplit(".", 1)[0] + ".mp4"
    with urllib.request.urlopen(urllib.request.Request(video, method="HEAD"), timeout=30) as r:
        if r.status != 200:
            sys.exit(f"Video not reachable: {video}")
    inp = {"channelId": CHANNEL_ID, "text": post["caption"], "schedulingType": "automatic",
           "assets": [{"video": {"url": video}}],
           "metadata": {"instagram": {"type": "reel", "shouldShareToFeed": True}}}
    inp.update({"mode": "customScheduled", "dueAt": utc_str(due)} if due else {"mode": "shareNow"})
    res = gql('''mutation($input: CreatePostInput!){ createPost(input:$input){ __typename
      ... on PostActionSuccess { post { id status dueAt } } ... on MutationError { message } } }''', {"input": inp})["createPost"]
    if res["__typename"] != "PostActionSuccess":
        sys.exit(f"Post failed: {res}")
    return res["post"]

def tiktok_caption(caption):
    body = caption.split("\nIllustration:")[0].strip()
    sents = re.split(r"(?<=[.!?])\s+", body)
    qi = next((i for i in range(len(sents) - 1, 0, -1) if sents[i].endswith("?")), None)
    text = sents[0]
    if qi is not None:
        q = sents[qi]
        if len(q.split()) < 7 and qi - 1 > 0:  # short question ("Would you try it?") needs its setup
            q = sents[qi - 1] + " " + q
        text += " " + q
    credit = next((l for l in caption.splitlines() if l.startswith("Illustration:")), "Illustration: Laurence Fellows")
    return text + "\n" + credit + "\n#oldmoney #menswear #vintagefashion #tailoringtraditionsclub"

def create_story(post, due):
    video = BASE + post["file"].rsplit(".", 1)[0] + ".mp4"
    res = gql('''mutation($input: CreatePostInput!){ createPost(input:$input){ __typename
      ... on PostActionSuccess { post { id } } ... on MutationError { message } } }''',
      {"input": {"channelId": CHANNEL_ID, "text": "", "schedulingType": "automatic", "mode": "customScheduled",
                 "dueAt": utc_str(due), "assets": [{"video": {"url": video}}],
                 "metadata": {"instagram": {"type": "story", "shouldShareToFeed": False}}}})["createPost"]
    if res["__typename"] != "PostActionSuccess":
        print(f"Story not scheduled yet: {res.get('message', res)}")
        return None
    return res["post"]["id"]

def create_tiktok(post, due):
    video = BASE + post["file"].rsplit(".", 1)[0] + ".mp4"
    res = gql('''mutation($input: CreatePostInput!){ createPost(input:$input){ __typename
      ... on PostActionSuccess { post { id } } ... on MutationError { message } } }''',
      {"input": {"channelId": TIKTOK_ID, "text": tiktok_caption(post["caption"]), "schedulingType": "automatic",
                 "mode": "customScheduled", "dueAt": utc_str(due), "assets": [{"video": {"url": video}}],
                 "metadata": {"tiktok": {"isAiGenerated": False}}}})["createPost"]
    if res["__typename"] != "PostActionSuccess":
        sys.exit(f"TikTok post failed: {res}")
    return res["post"]["id"]

now = datetime.datetime.now(datetime.timezone.utc)
added = 0
if "--now" in sys.argv and state["next"] < len(posts):
    p = create(posts[state["next"]])
    state["log"].append({"n": state["next"] + 1, "file": posts[state["next"]]["file"], "buffer_id": p["id"], "at": utc_str(now), "mode": "now"})
    state["next"] += 1; added += 1

waiting = [e for e in state["log"] if datetime.datetime.strptime(e["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc) > now]
last = max([datetime.datetime.strptime(e["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc) for e in state["log"]] + [now])
while len(waiting) < AHEAD and state["next"] < len(posts):
    slot = next_slot(last)
    post = posts[state["next"]]
    p = create(post, slot)
    entry = {"n": state["next"] + 1, "file": post["file"], "buffer_id": p["id"], "at": utc_str(slot)}
    state["log"].append(entry); waiting.append(entry)
    state["next"] += 1; last = slot; added += 1
    print(f"Scheduled {entry['n']}: {post['file']} for {slot:%a %b %d %I:%M %p %Z}")

done_tt = set(state.setdefault("tiktok_done", []))
for e in state["log"]:
    due = datetime.datetime.strptime(e["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    if due > now and due.astimezone(CT).hour == 17 and "tiktok_id" not in e and e["file"] not in done_tt:
        e["tiktok_id"] = create_tiktok(posts[e["n"] - 1], due)
        done_tt.add(e["file"]); added += 1
        print(f"TikTok {e['n']}: {e['file']} for {due.astimezone(CT):%a %b %d %I:%M %p %Z}")
state["tiktok_done"] = sorted(done_tt)

# Share each Instagram Reel to Stories 2 hours after it posts (soonest first, within Buffer's 10-post limit).
def is_future(t): return datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc) > now
reels_waiting = [e for e in state["log"] if is_future(e["at"])]
stories_waiting = [e for e in state["log"] if e.get("story_at") and is_future(e["story_at"])]
room = IG_LIMIT - len(reels_waiting) - len(stories_waiting)
for e in sorted(reels_waiting, key=lambda e: e["at"]):
    if room <= 0: break
    if "story_id" in e: continue
    due = datetime.datetime.strptime(e["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc) + datetime.timedelta(hours=2)
    sid = create_story(posts[e["n"] - 1], due)
    if not sid: break
    e["story_id"], e["story_at"] = sid, utc_str(due); room -= 1; added += 1
    print(f"Story {e['n']}: {e['file']} for {due.astimezone(CT):%a %b %d %I:%M %p %Z}")

json.dump(state, open("scheduler/state.json", "w"), indent=1)
print(f"Added {added}; {len(waiting)} waiting in Buffer; {len(posts) - state['next']} left in queue.")
