import requests
from bs4 import BeautifulSoup
import time
import re
import json
import sys
import random
import math

# the art of bodging doesn't care about beauty
# IT WILL BE JANKY AND YOU ARE GONNA LIKE IT

requestSession = requests.Session()
requestSession.headers['User-Agent'] = "roblox_mgs_leaderboard github action"

def requestURL(url, retryAmount=8):
    tries = 0
    print(f"Requesting {url}...")
    for _ in range(retryAmount):
        tries += 1
        try:
            response = requestSession.get(url)
            if response.status_code == 200:
                return response
            response.raise_for_status()
        except requests.exceptions.Timeout:
            print("Timed out!")
            print(f"Request failed: {e}")
        except requests.exceptions.TooManyRedirects:
            print("Too many redirects!")
            print(f"Request failed: {e}")
            return False
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                print("Too many requests!")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return False
        if tries < retryAmount:
            sleep_time = random.randint(
                math.floor(2 ** (tries - 0.5)),
                math.floor(2 ** tries)
                )
            print("Sleeping", sleep_time, "seconds.")
            time.sleep(sleep_time)
    return False
    
check = requestURL("https://metagamerscore.com/")
#check = requestURL("https://httpstat.us/429")
if check == False:
    print("MGS is giving an error; skipping extraction for now...")
    sys.exit(1)

print(f"MGS status code: {check.status_code}")
print(f"MGS response headers:\n{check.headers}")
requestSession.cookies = check.cookies
#print(a)

def extractTable(table):
    data_list = []

    rows = table.find_all('tr')

    for row in rows[1:]:
        cells = row.find_all('td')
        #print(f"cells: {cells}") # a bit too verbose but just in case
        rank = cells[0].get_text(strip=True)

        user_link = ""

        # reminder, there are hidden accounts. check in incognito mode in case the user is not found due to them being a hidden account (takes 1 minute, saves 1 hour)
        user_element = cells[1].find_all('a', attrs={'href': True, 'name': True})
        print(f"user_element: {user_element}")
        if user_element:
            user_link = user_element[0]['href']

        score = cells[2].get_text(strip=True).replace('\u202f', '')

        data_list.append([rank, user_link, score])

    return data_list

def getMetaGamerScore_leaderboard_stats(type):
    data_dict = {}

    for x in range(1, 3):
        #pageNum = 1
        #print(x)
        url = f"https://metagamerscore.com/platform_toplist/roblox/{str(type)}?page={x}"
        req = requestURL(url)
        print(f"Response status code: {req.status_code}")

        if req.ok:
            soup = BeautifulSoup(req.text, 'html.parser')
            table = soup.find('table')
            table_data = extractTable(table)
            
            for rank, user_link, score in table_data:
                data_dict[rank] = {
                    "mgs_link": user_link,
                    "score": score
                }

    if data_dict == {}: # page error?
        print("Nothing has been found; something went completely wrong")
        return False
    return data_dict

#print(data_dict)

whosWho = {}
def getUserIds(data_dict):
    for rank in data_dict:
        mgs_link = data_dict[rank]['mgs_link']

        if mgs_link == "":
            print(f"No MGS profile for rank {str(rank)}; profile hidden from public / not found when importing table...")
            data_dict[rank]['roblox_id'] = None
            continue

        if mgs_link in whosWho:
            print(f"Already checked {str(mgs_link)}")
            data_dict[rank]['roblox_id'] = whosWho[mgs_link]
            continue

        url = f"https://metagamerscore.com{mgs_link}?tab=accounts"
        req = requestURL(url)
        print(f"Response status code: {req.status_code}")

        if req.ok:
            soup = BeautifulSoup(req.text, 'html.parser')

            pattern = re.compile(r'https://www\.roblox\.com/users/\d+/profile')
            
            profile_links = soup.find_all('a', href=pattern)
            
            if profile_links == []:
                data_dict[rank]['roblox_id'] = None
                print("No Roblox User ID detected; profile hidden their gaming accounts from public...")
                continue

            for link in profile_links:
                #print(link['href'])
                pattern = r'https://www\.roblox\.com/users/(\d+)/profile'

                match = re.search(pattern, link['href'])

                if match:
                    user_id = match.group(1)
                    print(f"{str(mgs_link)} is Roblox User ID {str(user_id)}")
                    data_dict[rank]['roblox_id'] = int(user_id)
                    whosWho[mgs_link] = int(user_id)
                    #time.sleep(.75)
                    continue
                else:
                    print(f"No match found for {str(mgs_link)}")
        else:
            print("Request is not ok! Printing text:")
            print(req.text)

testing = False

# https://metagamerscore.com/platform_toplist/roblox/score
# https://metagamerscore.com/platform_toplist/roblox/completist
# https://metagamerscore.com/platform_toplist/roblox/firsts

categories = ["score", "completist", "firsts"]

for category in categories:
    print(f"Getting category [{category}]...")
    toplist_dict = getMetaGamerScore_leaderboard_stats(category)
    if toplist_dict == False:
        print(toplist_dict)
    else:
        print("Grabbed list successfully!")

        print("Dumping JSON as of now to console...")
        print(toplist_dict)

        print(f"Getting User IDs from {category}...")
        getUserIds(toplist_dict)

        print("Dumping finished JSON to console...")
        print(toplist_dict)

        json_file_path = f'{category}_rblx.json'
        print("Saving data...")
        if not testing:
            with open(json_file_path, 'w') as json_file:
                json.dump(toplist_dict, json_file, indent=4)
                print(f'Data saved to {json_file_path}')
                json_file.close()
        else:
            print("Testing mode; not saving (if this is on actions tell the village idiot to make that value False!)")