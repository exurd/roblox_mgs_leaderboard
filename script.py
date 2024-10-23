import requests, http.client
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
import os, time, re, json, sys, random, math, base64

# the art of bodging doesn't care about beauty
# IT WILL BE JANKY AND YOU ARE GONNA LIKE IT

requestSession = requests.Session()
requestSession.headers['User-Agent'] = UserAgent( # "roblox_mgs_leaderboard github action"
        os="linux",
        platforms="pc",
        browsers="firefox"
        ).random

print(f"User Agent: {requestSession.headers['User-Agent']}")

def requestURL(url, retryAmount=8, allow404=False):
    tries = 0
    print(f"Requesting {url}...")
    for _ in range(retryAmount):
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
            if allow404 and response.status_code == 404:
                return response
            print("HTTPError exception was called!")
            print(f"Request failed: {e}")
        except requests.exceptions.RequestException as e:
            print("RequestException!")
            print(f"Request failed: {e}")
            return False
        if tries < retryAmount:
            sleep_time = random.randint(
                math.floor(2 ** (tries - 0.5)),
                math.floor(2 ** tries)
                )
            print("Sleeping", sleep_time, "seconds.")
            time.sleep(sleep_time)
    print("Out of tries!")
    return None
    
check = requestURL("https://metagamerscore.com/")
#check = requestURL("https://httpstat.us/429")
if check == False:
    print("MGS is giving an error; skipping extraction for now...")
    sys.exit(1)
if check == None:
    print("Out of tries when requesting MGS; skipping extraction for now...")
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

def check_if_last_page(data_pagy):
    try:
        decode = base64.b64decode(data_pagy).decode('utf-8')
        jason = json.loads(decode)
        for key, value in jason[1].items():
            jason[1][key] = value.encode('utf-8').decode('unicode_escape')
        after = jason[1].get('after', '')
        is_last_page = 'disabled' in after
        return is_last_page
    except:
        return False

def getMetaGamerScore_leaderboard_stats(type):
    data_dict = {}

    pageNum = 1
    attempt = 0
    #lastFirstProfileOnPage = ""
    while True:
        #pageNum = 1
        #print(x)
        url = f"https://metagamerscore.com/platform_toplist/roblox/{str(type)}?page={pageNum}"
        req = requestURL(url)

        if attempt >= 3:
            print(f"Out of attempts for getMetaGamerScore_leaderboard_stats loop on [{str(type)}]; breaking loop!")
            break
        elif attempt != 0:
            print("Trying again...")

        if req == None:
            print("requestURL ran out of attempts...")
            attempt += 1
            continue
        elif req == False:
            print("requestURL returned False...")
            attempt += 1
            continue

        if req.ok:
            attempt = 0
            soup = BeautifulSoup(req.text, 'html.parser')
            table = soup.find('table')
            table_data = extractTable(table)
            
            # while i could base64 decode the <nav> data-pagy, this is 10x easier to handle. ...it could go wrong if mass amounts rapidly join the leaderboard...
            # ...what if the first profile on the page has their account hidden from guests? then the loop would keep going... not good, not good at all...
            # firstProfileOnPage = table_data[0][1]
            # if lastFirstProfileOnPage == firstProfileOnPage:
            #     print(f"{str(firstProfileOnPage)} is the same as {str(lastFirstProfileOnPage)}; no more pages to scan for [{str(type)}]")
            #     print("Breaking loop...")
            #     break
            # lastFirstProfileOnPage = firstProfileOnPage

            print(f"Adding page {str(pageNum)}'s table to table_data...")
            for rank, user_link, score in table_data:
                data_dict[rank] = {
                    "mgs_link": user_link,
                    "score": score
                }

            print("Checking data-pagy...")
            data_pagy = soup.find('nav', class_='pagy-nav-js').get('data-pagy')
            if check_if_last_page(data_pagy) == True:
                print("No more pages! Breaking loop...")
                break

            print("Going to next page...")
            pageNum += 1
        else:
            print(f"Response status code: {req.status_code}")
            attempt += 1

    if data_dict == {}: # page error?
        print("Nothing has been found; something went completely wrong")
        return False
    return data_dict

robloxApiStatus = True
userAccountStatus = {} # True = exists, False = doesn't exist
def checkAccountStatus(user_id):
    if user_id in userAccountStatus:
        return userAccountStatus[user_id]

    global robloxApiStatus
    if robloxApiStatus == False:
        return True

    print(f"Checking account status for {str(user_id)}...")
    req = requestURL(f"https://users.roblox.com/v1/users/{str(user_id)}", allow404=True)

    if req == None or req == False:
        print("Roblox APIs are most likely down... Avoiding for this session...")
        print(f"req: {req}")
        robloxApiStatus = False
        return True

    if req.status_code == 404:
        userAccountStatus[user_id] = False
    else:
        userAccountStatus[user_id] = True
    return userAccountStatus[user_id]

cache_folder = os.path.join(os.path.dirname(__file__), ".cache")
os.makedirs(cache_folder, exist_ok=True)
print(f"cache_folder: [{cache_folder}]")

def load_data(filename):
    print(f"Loading data from [{filename}]...")
    data_file_path = os.path.join(cache_folder, filename)
    if os.path.exists(data_file_path) and os.path.getsize(data_file_path) > 0:
        with open(data_file_path, "r") as f:
            data = json.load(f)
            f.close()
    else:
        data = {}
    return data

def save_data(data,filename):
    print(f"Saving data to [{filename}]...")
    data_file_path = os.path.join(cache_folder, filename)
    with open(data_file_path, "w") as f:
        json.dump(data, f, indent=4, sort_keys=True)
        f.close()

whosWho = load_data("mgs_profiles.json")
print(f"whosWho cache: {whosWho}")
if whosWho == {}:
    whosWho["_TIMESTAMP"] = time.time()
else:
    if (time.time() - whosWho["_TIMESTAMP"]) > (86400*3): # 3 day cache
        print("whosWho's timestamp older than current timestamp, clearing cache...")
        whosWho = {}
    whosWho["_TIMESTAMP"] = time.time()
def getUserIds(data_dict):
    for rank in data_dict:
        mgs_link = data_dict[rank]['mgs_link']

        if mgs_link == "":
            print(f"No MGS profile for rank {str(rank)}; profile hidden from public / not found when importing table...")
            data_dict[rank]['roblox_id'] = None
            continue

        if mgs_link in whosWho:
            print(f"{str(mgs_link)} is in cache...")
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
                whosWho[mgs_link] = None
                print("No Roblox User ID detected; profile hidden their gaming accounts from public...")
                continue

            for link in profile_links:
                #print(link['href'])
                pattern = r'https://www\.roblox\.com/users/(\d+)/profile'

                match = re.search(pattern, link['href'])

                if match:
                    user_id = match.group(1)
                    print(f"{str(mgs_link)} is Roblox User ID {str(user_id)}")
                    if checkAccountStatus(user_id):
                        data_dict[rank]['roblox_id'] = int(user_id)
                        whosWho[mgs_link] = int(user_id)
                    else:
                        print(f"checkAccountStatus returned False, setting to None")
                        data_dict[rank]['roblox_id'] = None
                        whosWho[mgs_link] = None
                    #time.sleep(.75)
                    continue
                else:
                    print(f"No match found for {str(mgs_link)}")
        else:
            print("Request is not ok! Printing text:")
            print(req.text)
    save_data(whosWho,"mgs_profiles.json")

testing = False

# https://metagamerscore.com/platform_toplist/roblox/score
# https://metagamerscore.com/platform_toplist/roblox/completist
# https://metagamerscore.com/platform_toplist/roblox/firsts

categories = ["score", "completist", "firsts"]

for category in categories:
    print(f"Getting category [{category}]...")
    toplist_dict = getMetaGamerScore_leaderboard_stats(category)
    if toplist_dict == False:
        print("toplist_dict is False...")
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