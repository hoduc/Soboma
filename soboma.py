import requests
import ConfigPaser

CONFIG_FILE_NAME = r'config'
TWITTER_CONFIG_SECTION = r'twitter'
SEARCH_URL_KEY = r'search_url'

twitter_config = ConfigParser.ConfigParser()
config.readfp(open(CONFIG_FILE_NAME))
search_url = config.get(TWITTER_CONFIG_SECTION, SEARCH_URL_KEY)
babylon_search_url = search_url + 'babylon'

r = requests.get(babylon_search_url)
if r.status_code == 200:    
    print(r.json())    
else:
    print("Got status:", r.status_code)
    print(r)




