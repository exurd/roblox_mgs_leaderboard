"""
Roblox MetaGamerScore Leaderboard - script.py

Licensed under the GNU General Public License Version 3.0
(see below for more details)
"""
import os
import time
import re
import json
import sys
import random
import math
import base64
import http.client

import requests
from fake_useragent import UserAgent
from bs4 import BeautifulSoup


# the art of bodging doesn't care about beauty
# IT WILL BE JANKY AND YOU ARE GONNA LIKE IT


TESTING = False


requestSession = requests.Session()
requestSession.headers["User-Agent"] = UserAgent(
        os="Linux",
        platforms="desktop",
        browsers="Firefox"
        ).random
print(f"User Agent: {requestSession.headers["User-Agent"]}")

data_pagy_pattern = re.compile(r'data-pagy="([a-zA-Z0-9\/]+(?:=|==)?)"')

def request_url(url, retry_amount=8, allow_404=False):
    """
    Request a URL until it succeeds or after an amount of attempts.

    The rate limit sleep code was derived from
    ArchiveTeam/roblox-marketplace-comments-grab, which is under The Unlicense.
    For more information, please refer to https://unlicense.org.
    """
    tries = 0
    print(f"Requesting {url}...")
    for _ in range(retry_amount):
        tries += 1
        try:
            response = requestSession.get(url)
            if response.status_code == 200:
                return response
            response.raise_for_status()
        except http.client.RemoteDisconnected as e:
            print("The server closed the connection unexpectedly!")
            print(f"Request failed: {e}")
        except requests.exceptions.Timeout as e:
            print("The request timed out!")
            print(f"Request failed: {e}")
        except requests.exceptions.ConnectionError as e:
            print("Could not connect to the server!")
            print(f"Request failed: {e}")
        except requests.exceptions.TooManyRedirects as e:
            print("Too many redirects!")
            print(f"Request failed: {e}")
            return False
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                print("429: Too many requests!")
            if allow_404 and response.status_code == 404:
                return response
            print("HTTPError exception was called!")
            print(f"Request failed: {e}")
        except requests.exceptions.RequestException as e:
            print("RequestException!")
            print(f"Request failed: {e}")
            return False
        if tries < retry_amount:
            sleep_time = random.randint(
                math.floor(2 ** (tries - 0.5)),
                math.floor(2 ** tries)
                )
            print("Sleeping", sleep_time, "seconds.")
            time.sleep(sleep_time)
    print("Out of tries!")
    return None


check = request_url("https://metagamerscore.com/")
if check is False:
    print("MGS is giving an error; skipping extraction for now...")
    sys.exit(1)
if check is None:
    print("Out of tries when requesting MGS; skipping extraction for now...")
    sys.exit(1)
print(f"MGS status code: {check.status_code}")
print(f"MGS response headers:\n{check.headers}")
requestSession.cookies = check.cookies


def extract_table_info(table):
    """Extracts rank, score and user_link information from a table"""
    data_list = []

    rows = table.find_all("tr")

    for row in rows[1:]:
        cells = row.find_all("td")
        # print(f"cells: {cells}")  # a bit too verbose but just in case
        rank = cells[0].get_text(strip=True)

        user_link = ""

        # reminder, there are hidden accounts. check in incognito mode in case
        # the user is not found due to them being a hidden account
        # (takes 1 minute, saves 1 hour)
        user_element = cells[1].find_all("a", attrs={"href": True, "name": True})

        print(f"user_element: {user_element}")
        if user_element:
            user_link = user_element[0]["href"]

        score = cells[2].get_text(strip=True).replace("\u202f", "")

        data_list.append([rank, user_link, score])

    return data_list


def check_if_last_page(data_pagy):
    """Decodes the data-pagy variable to see if it's the last page."""
    try:
        decode = base64.b64decode(data_pagy).decode("utf-8")
        jason = json.loads(decode)
        for key, value in jason[1].items():
            jason[1][key] = value.encode("utf-8").decode("unicode_escape")
        after = jason[1].get("after", "")
        is_last_page = "disabled" in after
        return is_last_page
    except Exception as e:
        print(f"Decoding went wrong: {e}")
        return False


def get_mgs_leaderboard_stats(mgs_type):
    """
    Goes though each page of mgs_type and parses the information into a data_dict
    """
    data_dict = {}
    page_num = 1
    attempt = 0
    pagy_works = True

    while True:
        url = f"https://metagamerscore.com/platform_toplist/roblox/{str(mgs_type)}?page={page_num}"
        req = request_url(url)

        if attempt >= 3:
            print("Out of attempts for getMetaGamerScore_leaderboard_stats "
                  f"loop on [{str(mgs_type)}]; breaking loop!")
            break

        if attempt != 0:
            print("Trying again...")

        if req is None:
            print("requestURL ran out of attempts...")
            attempt += 1
            continue

        if req is False:
            print("requestURL returned False...")
            attempt += 1
            continue

        if req.ok:
            attempt = 0
            soup = BeautifulSoup(req.text, "html.parser")
            table = soup.find("table")
            table_data = extract_table_info(table)

            print(f"Adding page {str(page_num)}'s table to table_data...")
            for rank, user_link, score in table_data:
                data_dict[rank] = {
                    "mgs_link": user_link,
                    "score": score
                }

            if pagy_works:
                print("Checking data-pagy...")

                # data_pagy = soup.find("nav", class_="pagy-nav-js").get("data-pagy")
                # not doing the above anymore because a website update added a space
                # inbetween `pagy` and `nav-js`
                data_pagy = data_pagy_pattern.search(req.text)

                print(f"data_pagy: {data_pagy}")
                if data_pagy:
                    print(f"data_pagy matches: {data_pagy.groups()}")
                    if check_if_last_page(data_pagy.group(1)) is True:
                        print("No more pages! Breaking loop...")
                        break
                else:
                    print("data-pagy is most likely broken, only getting 3 pages...")
                    pagy_works = False
            elif page_num == 3:
                print("data-pagy broken; got 3 pages, breaking loop...")
                break

            print("Going to next page...")
            page_num += 1
        else:
            print(f"Response status code: {req.status_code}")
            attempt += 1

    if data_dict == {}:  # page error?
        print("Nothing has been found; something went completely wrong")
        return False
    return data_dict


roblox_api_status = True
user_account_status: dict[int, bool] = {}


def check_account_status(user_id):
    """
    Checks an Roblox account's status.

    True = account exists, False = account does not exist / no longer exists
    """
    if user_id in user_account_status:
        return user_account_status[user_id]

    global roblox_api_status
    if roblox_api_status is False:
        return False

    print(f"Checking account status for {str(user_id)}...")
    req = request_url(f"https://users.roblox.com/v1/users/{str(user_id)}", allow_404=True)

    if req is None or req is False:
        print("Roblox APIs are most likely down... "
              "Avoiding for this session...")
        print(f"req: {req}")
        roblox_api_status = False
        return False

    if req.status_code == 404:
        user_account_status[user_id] = False
    else:
        user_account_status[user_id] = True
    return user_account_status[user_id]


cache_folder = os.path.join(os.path.dirname(__file__), ".cache")
os.makedirs(cache_folder, exist_ok=True)
print(f"cache_folder: [{cache_folder}]")


def load_data(filename):
    """Load data from a JSON file."""
    print(f"Loading data from [{filename}]...")
    data_file_path = os.path.join(cache_folder, filename)
    if os.path.exists(data_file_path) and os.path.getsize(data_file_path) > 0:
        with open(data_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            f.close()
    else:
        data = {}
    return data


def save_data(data, filename):
    """
    Save data to a JSON file.
    """
    if not TESTING:
        print(f"Saving data to [{filename}]...")
        data_file_path = os.path.join(cache_folder, filename)
        with open(data_file_path, "w", encoding="utf-8", newline="\r\n") as f:
            json.dump(data, f, indent=4, sort_keys=True)
            print(f"Data saved to {data_file_path}")
            f.close()


whosWho = load_data("mgs_profiles.json")
print(f"whosWho cache: {whosWho}")
currentTime = time.time()
if whosWho == {}:
    whosWho["_TIMESTAMP"] = currentTime
else:
    if (currentTime - whosWho["_TIMESTAMP"]) > (86400 * 14):  # 2 weeks cache
        print(f"whosWho's timestamp ({whosWho["_TIMESTAMP"]}) older than "
              f"current timestamp ({currentTime}), clearing cache...")
        whosWho = {}
        whosWho["_TIMESTAMP"] = currentTime


user_pattern_no_select = re.compile(r"https://www\.roblox\.com/users/\d+/profile")
user_pattern = re.compile(r"https://www\.roblox\.com/users/(\d+)/profile")


def get_user_ids(data_dict):
    """Finds and adds Roblox User IDs from MGS profiles in a specified data_dict"""
    for rank in data_dict:
        mgs_link = data_dict[rank]["mgs_link"]

        if mgs_link == "":
            print(f"No MGS profile for rank {str(rank)}; profile hidden "
                  "from public / not found when importing table...")
            data_dict[rank]["roblox_id"] = None
            continue

        if mgs_link in whosWho:
            print(f"{str(mgs_link)} is in cache...")
            data_dict[rank]["roblox_id"] = whosWho[mgs_link]
            continue

        url = f"https://metagamerscore.com{mgs_link}?tab=accounts"
        req = request_url(url)
        print(f"Response status code: {req.status_code}")

        if req.ok:
            soup = BeautifulSoup(req.text, "html.parser")
            profile_links = soup.find_all("a", href=user_pattern_no_select)

            if profile_links == []:
                data_dict[rank]["roblox_id"] = None
                whosWho[mgs_link] = None
                print("No Roblox User ID detected; "
                      "profile hid their gaming accounts from public...")
                continue

            for link in profile_links:
                match = user_pattern.search(link["href"])
                if match:
                    user_id = match.group(1)
                    print(f"{str(mgs_link)} is Roblox User ID {str(user_id)}")
                    if check_account_status(user_id):
                        data_dict[rank]["roblox_id"] = int(user_id)
                        whosWho[mgs_link] = int(user_id)
                    else:
                        print("checkAccountStatus returned False "
                              f"for {mgs_link}, "
                              "setting roblox_id to None")
                        data_dict[rank]["roblox_id"] = None
                        whosWho[mgs_link] = None
                    continue
                print(f"No match found for {str(mgs_link)}")
        else:
            print("Request is not ok! Printing text:")
            print(req.text)
    save_data(whosWho, "mgs_profiles.json")


# current platform_toplists for roblox:
# https://metagamerscore.com/platform_toplist/roblox/score
# https://metagamerscore.com/platform_toplist/roblox/completist
# https://metagamerscore.com/platform_toplist/roblox/firsts

categories = ["score", "completist", "firsts"]

if __name__ == "__main__":
    for category in categories:
        print(f"Getting category [{category}]...")
        toplist_dict = get_mgs_leaderboard_stats(category)
        if toplist_dict is False:
            print("toplist_dict is False...")
        else:
            print("Grabbed list successfully!")

            print("Dumping JSON as of now to console...")
            print(toplist_dict)

            print(f"Getting User IDs from {category}...")
            get_user_ids(toplist_dict)

            print("Dumping finished JSON to console...")
            print(toplist_dict)

            json_file_path = f"{category}_rblx.json"
            if not TESTING:
                with open(json_file_path, "w", encoding="utf-8", newline="\r\n") as json_file:
                    json.dump(toplist_dict, json_file, indent=4)
                    print(f"Data saved to {json_file_path}")
                    json_file.close()
            else:
                print("Testing mode; not saving (if this is on actions tell "
                      "the village idiot to set that value to False!)")


# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
