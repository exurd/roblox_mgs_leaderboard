import requests
from bs4 import BeautifulSoup
import time
import re
import json

# the art of bodging doesn't care about beauty
# IT WILL BE JANKY AND YOU ARE GONNA LIKE IT

requestSession = requests.Session()
adapter = requests.adapters.HTTPAdapter(max_retries=5)
requestSession.mount('https://', adapter)
requestSession.mount('http://', adapter)
requestSession.headers['User-Agent'] = "roblox_mgs_leaderboard github action"

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
        req = requestSession.get(url)

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

# yes, i know this is wasteful, but it is quick and the fix would take an hour more to do so i don't care >:)
def getUserIds(data_dict):
    for rank in data_dict:
        mgs_link = data_dict[rank]['mgs_link']
        if mgs_link == "":
            print("No MGS profile; profile hidden from public / not found when importing table...")
            data_dict[rank]['roblox_id'] = None
            continue
        url = f"https://metagamerscore.com{mgs_link}?tab=accounts"
        #print(url)

        req = requestSession.get(url)

        print(f"Status Code {req.status_code}")

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
                    time.sleep(.75)
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