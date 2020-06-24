import requests
import configparser
from fake_useragent import UserAgent

UA = UserAgent()
HEADER = {'User-Agent' : str(UA.chrome) }
CONFIG_FILE_NAME = "config"
TWITTER_CONFIG_SECTION = "twitter"
SEARCH_URL_KEY = "search_url"

twitter_config = configparser.ConfigParser()
twitter_config.read(CONFIG_FILE_NAME)
search_url = twitter_config[TWITTER_CONFIG_SECTION][SEARCH_URL_KEY]
babylon_search_url = search_url + "babylon"

r = requests.get(babylon_search_url, headers=HEADER)
if r.status_code == 200:    
    print(r.json())
else:
    print("Got status:", r.status_code)
    print(r)




