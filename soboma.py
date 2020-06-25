import requests
import configparser
from fake_useragent import UserAgent
from bs4 import BeautifulSoup


UA = UserAgent()
HEADER = {'User-Agent' : str(UA.chrome) }
CONFIG_FILE_NAME = "config"
TWITTER_CONFIG_SECTION = "twitter"
SEARCH_URL_KEY = "search_url"
TWITTER_IDS_KEY = "twitter_ids"
DEBUG_KEY = "debug"

twitter_config = configparser.ConfigParser()
twitter_config.read(CONFIG_FILE_NAME)
search_url = twitter_config[TWITTER_CONFIG_SECTION][SEARCH_URL_KEY]
twitter_ids = twitter_config[TWITTER_CONFIG_SECTION][TWITTER_IDS_KEY].split(",")
debug = twitter_config[TWITTER_CONFIG_SECTION][DEBUG_KEY]

for twitter_id in twitter_ids:
    r = requests.get(search_url + twitter_id, headers=HEADER)
    if r.status_code == 200:    
        json = r.json()
        html_doc = json['items_html']
        soup = BeautifulSoup(html_doc, 'html.parser')
        lis = soup.find_all("li")
        profile_li = lis[0]
        profile_img = profile_li.find("img", class_ = "ProfileCard-avatarImage")["src"]
        #[tweets, followings, followers]
        profile_stats = ["".join(elem.get_text().split()) for elem in profile_li.find_all("span", class_ = "ProfileCardStats-statValue")]
        profile_bio = profile_li.find("p", class_ = "ProfileCard-bio").get_text()
        profile_location = profile_li.find("p", class_ = "ProfileCard-locationAndUrl").get_text()
        profile_elem = (profile_img, profile_stats, profile_bio, profile_location)
        print(profile_elem)
        if debug:
            with open(twitter_id + ".html", "w", encoding = "utf-8") as html_file:            
                html_file.write(soup.prettify())
    else:
        print("Got status:", r.status_code)
        print(r)
    
        
    

    







