# --- Import libraries ---
import json
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv
import os
import argparse
from colorama import Fore, Style

# --- Configuration ---
load_dotenv()
JELLYFIN_URL = os.getenv("JELLYFIN_URL")
API_KEY = os.getenv("API_KEY")
MEDIA_PATH = os.getenv("MEDIA_PATH") or ""
PATHS_FILE = os.getenv("PATHS_FILE") or "paths.txt"

HEADERS = {
    "X-Emby-Token": API_KEY
}

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description="Jellywatched - Jellyfin Watched Items Tool")
parser.add_argument("-u", "--users", nargs="+", help="List of usernames to compare watched items")
parser.add_argument("-a", "--all", action="store_true", help="Compare watched items for all users")
parser.add_argument("-p", "--paths", action="store_true", help="Output paths to file")
args = parser.parse_args()

# --- Jellyfin API Functions ---
def jellyfin_get_all_usernames():
    r = requests.get(f"{JELLYFIN_URL}/Users", headers=HEADERS, timeout=10)
    r.raise_for_status()

    return [user["Name"] for user in r.json()]

def jellyfin_get_user_id_by_name(username):
    r = requests.get(f"{JELLYFIN_URL}/Users", headers=HEADERS, timeout=10)
    r.raise_for_status()

    for user in r.json():
        if user["Name"].lower() == username.lower():
            return user["Id"]

    return None


def get_watched_items(user_id):
    url = f"{JELLYFIN_URL}/Users/{user_id}/Items"

    params = {
        "Filters": "IsPlayed",
        "Recursive": True,
        "Fields": "PrimaryImageAspectRatio,ProductionYear,Path,SeriesName,ParentIndexNumber,IndexNumber",
        "IncludeItemTypes": "Movie,Episode"
    }

    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()["Items"]

def watched(username):
    user_id = jellyfin_get_user_id_by_name(username)
    items = get_watched_items(user_id)

    result = []
    for item in items:
        result.append({
            "name": item.get("Name"),
            "series_name": item.get("SeriesName"),
            "season": item.get("ParentIndexNumber"),
            "episode": item.get("IndexNumber"),
            "type": item.get("Type"),
            "year": item.get("ProductionYear"),
            "path": item.get("Path"),
            "play_count": item.get("UserData", {}).get("PlayCount", 0)
        })

    return json.dumps(result, ensure_ascii=False, indent=2)

def watched_by_users(usernames):
    user_sets = []

    for username in usernames:
        user_id = jellyfin_get_user_id_by_name(username)
        if not user_id:
            print(f"{Style.BRIGHT}{Fore.RED}User not found: {username}{Style.RESET_ALL}")
            sys.exit(1)

        items = get_watched_items(user_id)

        paths = set(item.get("Path") for item in items if item.get("Path"))
        user_sets.append(paths)

    if not user_sets:
        return []

    common_paths = set.intersection(*user_sets)

    first_user_id = jellyfin_get_user_id_by_name(usernames[0])
    first_items = get_watched_items(first_user_id)

    result = []
    for item in first_items:
        if item.get("Path") in common_paths:
            result.append({
                "name": item.get("Name"),
                "series_name": item.get("SeriesName"),
                "season": item.get("ParentIndexNumber"),
                "episode": item.get("IndexNumber"),
                "type": item.get("Type"),
                "year": item.get("ProductionYear"),
                "path": item.get("Path"),
                "play_count": item.get("UserData", {}).get("PlayCount", 0)
            })

    return result

# --- Execution ---
paths_file = PATHS_FILE
if os.path.exists(paths_file) and args.paths:
    os.remove(paths_file)

if not (args.users or args.all or args.paths):
    parser.print_help()
    exit(0)

if args.all:
    common_watched = watched_by_users(jellyfin_get_all_usernames())

if args.users:
    common_watched = watched_by_users(args.users)

common_watched.sort(key=lambda x: x["name"].lower() if x["name"] else "")

if common_watched == []:
    print(Style.BRIGHT + Fore.YELLOW + "None of the specified users have any watched items in common." + Style.RESET_ALL)

if common_watched:
    print(f"{Style.BRIGHT}{Fore.YELLOW}Common watched items:{Style.RESET_ALL}\n")
    movies_print = False
    series_print = False
    others_print = False
    for i in common_watched:
        if i["type"] == "Episode":
            if not series_print:
                print(f"{Style.BRIGHT}{Fore.RED}Series:{Style.RESET_ALL}")
                series_print = True
            print(f"""{Style.BRIGHT}{Fore.MAGENTA}{i["series_name"]}{Style.RESET_ALL} - {Fore.CYAN}S{i["season"]:02d}E{i["episode"]:02d}{Style.RESET_ALL}""")
        elif i["type"] == "Movie":
            if not movies_print:
                print(f"{Style.BRIGHT}{Fore.RED}\nMovies:{Style.RESET_ALL}")
                movies_print = True
            print(f"""{Style.BRIGHT}{Fore.GREEN}{i["name"]}{Style.RESET_ALL}""")
        else:
            if not others_print:
                print(f"{Style.BRIGHT}{Fore.RED}\nOthers:{Style.RESET_ALL}")
                others_print = True
            print(f"""{Style.BRIGHT}{Fore.RED}{i["name"]}{Style.RESET_ALL} - Type: {i["type"]}""")
        if args.paths:
            with open(paths_file, "a", encoding="utf-8") as f:
                f.write(f"{MEDIA_PATH}{i['path']}\n")