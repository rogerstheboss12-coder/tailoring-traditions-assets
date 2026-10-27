"""Post the next Reel in posts.json to Instagram via Buffer. Run daily by GitHub Actions."""
import json, os, sys, datetime, urllib.request

API = "https://api.buffer.com"
ORG_ID = "6adfe7f4730bcfe1e394b79c"
CHANNEL_ID = "6adffc3a2f1f5ed648e313df"
EXPECTED_NAME = "tailoringtraditionsclub"
BASE = "https://rogerstheboss12-coder.github.io/tailoring-traditions-assets/final/"
TOKEN = os.environ["BUFFER_TOKEN"]

def gql(query, variables=None):
    req = urllib.request.Request(API, data=json.dumps({"query": query, "variables": variables or {}}).encode(),
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.load(r)
    if out.get("errors"):
        sys.exit(f"Buffer error: {out['errors']}")
    return out["data"]

posts = json.load(open("posts.json"))
state = json.load(open("scheduler/state.json"))
i = state["next"]
if i >= len(posts):
    print("All posts published."); sys.exit(0)
post = posts[i]

# Skip if something was posted in the last 20 hours (e.g. a manually scheduled test post).
last = state["log"][-1]["at"] if state["log"] else None
if last and datetime.datetime.utcnow() - datetime.datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ") < datetime.timedelta(hours=20):
    print(f"Skipping: last post was at {last}"); sys.exit(0)

# Safety: only ever post to the Tailoring Traditions Club Instagram channel.
chans = gql('query($o: OrganizationId!){ channels(input:{organizationId:$o}){ id name service } }', {"o": ORG_ID})["channels"]
chan = next((c for c in chans if c["id"] == CHANNEL_ID), None)
if not chan or chan["name"] != EXPECTED_NAME or chan["service"] != "instagram":
    sys.exit(f"Refusing to post: channel check failed ({chan})")

video = BASE + post["file"].rsplit(".", 1)[0] + ".mp4"
with urllib.request.urlopen(urllib.request.Request(video, method="HEAD"), timeout=30) as r:
    if r.status != 200:
        sys.exit(f"Video not reachable: {video}")

res = gql('''mutation($input: CreatePostInput!){ createPost(input:$input){ __typename
  ... on PostActionSuccess { post { id status } } ... on MutationError { message } } }''',
  {"input": {"channelId": CHANNEL_ID, "text": post["caption"], "schedulingType": "automatic", "mode": "shareNow",
             "assets": [{"video": {"url": video}}],
             "metadata": {"instagram": {"type": "reel", "shouldShareToFeed": True}}}})["createPost"]
if res["__typename"] != "PostActionSuccess":
    sys.exit(f"Post failed: {res}")

state["log"].append({"n": i + 1, "file": post["file"], "buffer_id": res["post"]["id"],
                     "at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")})
state["next"] = i + 1
json.dump(state, open("scheduler/state.json", "w"), indent=1)
print(f"Posted {i + 1}/{len(posts)}: {post['file']} -> {res['post']['id']}")
