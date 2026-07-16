import requests, json, re, questionary, pylast, time
from datetime import timedelta
from dateutil import parser

from dotenv import load_dotenv
import os

load_dotenv()

LF_API_KEY = os.getenv("LF_API_KEY")
LF_API_SEC = os.getenv("LF_API_SECRET")
LF_USERNAME = os.getenv("LF_USERNAME")
LF_PASSWORD = os.getenv("LF_PASSWORD")


# reusable json blob extractor
def get_next_data(url):
    # yeah basically all metadata is stored in a single __NEXT_DATA__ tag :yay:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        response.text, re.DOTALL
    )
    if not match:
        raise RuntimeError(f"Couldn't find __NEXT_DATA__ on page {url}")
    return json.loads(match.group(1))

# list eps from prog
def list_episodes(program_url):
    data = get_next_data(program_url)
    items = data["props"]["pageProps"]["programCollectionPrepared"]["items"]
    episodes = []

    for item in items:
        episodes.append({
            "title": item["cardTitle"],
            "url": "https://www.abc.net.au" + item["articleLink"]
                if item["articleLink"].startswith("/") else item["articleLink"], # idk this json is NOT consistent, sometimes its the slug sometimes its the full url
            "published": item["cardAttributionPrepared"]["publishedDate"],
        })
    return episodes

# interactive menu
# choose program maybe later
# def choose_program(programs):
#     pass

def choose_episode(episodes):
    choices = [
        questionary.Choice(title=f'{e["title"]} ({e["published"]})', value=e)
        for e in episodes
    ]
    return questionary.select("Pick an episode to scrobble:", choices).ask()

def ask_start_time():
    date_str = questionary.text("Session start date (YYYY-MM-DD):").ask()
    time_str = questionary.text("Session start time (HH:MM, 24h):").ask() # sacrificed the r in hr for the matching monospace :nvs:
    return parser.parse(f"{date_str} {time_str}")


# real extraction
def extract_tracklist(episode_url):
    data = get_next_data(episode_url)
    return data["props"]["pageProps"]["data"]["documentProps"]["tracklistPrepared"]["items"]

def parse_offset(ts): # basically u need to have a time for a scrobble to occur, so we use song lengths (timestampRelative in json blob) and do some math
    parts = [int(p) for p in ts.split(":")] # i.e. 04:12, mins and secs OR something like 01:02:51 
    if len(parts) == 2:
        m, s = parts
        return timedelta(minutes=m, seconds=s)
    if len(parts) == 3:
        h, m, s = parts
        return timedelta(hours=h, minutes=m, seconds=s)
    
    raise ValueError(f"Invalid timestamp: '{ts}', expected 'MM:SS' or 'HH:MM:SS'")
    

def calc_play_times(tracks, start_delta):
    for t in tracks:
        offset = parse_offset(t["timestamp"])
        yield {
            "artist": t["artist"],
            "title": t["title"],
            "played_at": start_delta + offset,
        }


# yeeting it over to last.fm api with pylast
# you need api key + secret ALONG with credentials to WRITE, to read u can just use api keys, but we arent doing that
def get_network():
    return pylast.LastFMNetwork(
        api_key=LF_API_KEY,
        api_secret=LF_API_SEC,
        username=LF_USERNAME,
        password_hash=pylast.md5(LF_PASSWORD),
    )

def scrobble_all(network: pylast.LastFMNetwork, scrobbles): # really need the intellisense here so adding types :pf:
    for s in scrobbles:
        network.scrobble(
            artist=s["artist"],
            title=s["title"],
            timestamp=int(s["played_at"].timestamp())
        )
        print("scrobbled :D")
        time.sleep(0.25) # be kind to the API :3

def main():
    program_url = questionary.text("Program URL:").ask()
    episodes = list_episodes(program_url)
    episode = choose_episode(episodes)
    start_delta = ask_start_time()

    tracks = extract_tracklist(episode["url"])
    scrobbles = list(calc_play_times(tracks, start_delta))

    for s in scrobbles:
        print(f'{s["played_at"]} {s["artist"]} - {s["title"]}')

    if questionary.confirm("Scrobble these to Last.fm?").ask():
        network = get_network()
        scrobble_all(network, scrobbles)
        print("Done!!")
if __name__ == "__main__":
    main()