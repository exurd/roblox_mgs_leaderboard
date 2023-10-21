import requests
from bs4 import BeautifulSoup
import time
import re
import json

# the art of bodging doesn't care about beauty
# IT WILL BE JANKY AND YOU ARE GONNA LIKE IT

def extractTable(table):
    data_list = []

    rows = table.find_all('tr')

    for row in rows[1:]:
        cells = row.find_all('td')
        rank = cells[0].get_text(strip=True)

        user_link = ""

        user_element = cells[1].find('a', href=True, title=True)
        if user_element:
            user_link = user_element['href']
        
        score = cells[2].get_text(strip=True).replace('\u202f', '')

        data_list.append([rank, user_link, score])

    return data_list

def getMetaGamerScore_leaderboard_stats(type):
    data_dict = {}

    for x in range(1, 3):
        #pageNum = 1
        #print(x)
        url = f"https://metagamerscore.com/platform_toplist/roblox/{str(type)}?page={x}"
        req = requests.get(url)

        if req.ok:
            soup = BeautifulSoup(req.text, 'html.parser')
            table = soup.find('table')
            table_data = extractTable(table)
            
            for rank, user_link, score in table_data:
                data_dict[rank] = {
                    "mgs_link": user_link,
                    "score": score
                }
    return data_dict

#print(data_dict)

# yes, i know this is wasteful, but it is quick and the fix would take an hour more to do so i don't care >:)
def getUserIds(data_dict):
    for rank in data_dict:
        mgs_link = data_dict[rank]['mgs_link']
        if mgs_link == "":
            data_dict[rank]['roblox_id'] = None
            continue
        url = f"https://metagamerscore.com{data_dict[rank]['mgs_link']}?tab=accounts"
        #print(url)

        req = requests.get(url)

        if req.ok:
            soup = BeautifulSoup(req.text, 'html.parser')

            pattern = re.compile(r'https://www\.roblox\.com/users/\d+/profile')
            
            profile_links = soup.find_all('a', href=pattern)
            
            if profile_links == []:
                data_dict[rank]['roblox_id'] = None
                continue

            for link in profile_links:
                #print(link['href'])
                pattern = r'https://www\.roblox\.com/users/(\d+)/profile'

                match = re.search(pattern, link['href'])

                if match:
                    user_id = match.group(1)
                    #print("User ID:", user_id)
                    data_dict[rank]['roblox_id'] = int(user_id)
                    time.sleep(.75)
                    continue
                else:
                    print(f"No match found for {link['href']}")

# https://metagamerscore.com/platform_toplist/roblox/score
score_dict = getMetaGamerScore_leaderboard_stats("score")
getUserIds(score_dict)

json_file_path = 'score_rblx.json'

with open(json_file_path, 'w') as json_file:
    json.dump(score_dict, json_file, indent=4)

print(f'Data saved to {json_file_path}')

# https://metagamerscore.com/platform_toplist/roblox/completist
completist_dict = getMetaGamerScore_leaderboard_stats("completist")
getUserIds(completist_dict)

json_file_path = 'completist_rblx.json'

with open(json_file_path, 'w') as json_file:
    json.dump(completist_dict, json_file, indent=4)

print(f'Data saved to {json_file_path}')
