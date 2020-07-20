import configparser
from util import DebugPrintLevel, current_debug_print_level, current_debug_print

CONFIG_FILE_NAME = "config"
COMMON_CONFIG_SECTION = "common"
WINDOW_TITLE_KEY = "window_title"
TWITTER_CONFIG_SECTION = "twitter"
CONSUMER_KEY = "consumer_key"
CONSUMER_SECRET = "consumer_secret"
ACCESS_TOKEN_KEY = "access_token_key"
ACCESS_TOKEN_SECRET = "access_token_secret"
USE_API_KEY = "use_api"
NUMBER_OF_TWEETS_KEY = "number_of_tweets"
STATUS_LINK_KEY = "status_link"
OPEN_STATUS_LINK_KEY = "open_status_link"
SEARCH_URL_KEY = "search_url"
TWITTER_IDS_KEY = "twitter_ids"
UI_KEY = "ui"
DEBUG_KEY = "debug"
DEBUG_BROWSER_KEY = "debug_browser"
DEBUG_BROWSER_VIEW_URL_KEY = "debug_browser_view_url"
DEBUG_PRINT_KEY = "debug_print"
DEBUG_HTML_KEY = "debug_html"
DEBUG_PRINT_LEVEL_KEY = "debug_print_level"
DEBUG_JSON_KEY = "debug_json"
NEXT_PAGE_KEY = "next_page_key"

config = configparser.ConfigParser()
config.read(CONFIG_FILE_NAME)
window_title = config[COMMON_CONFIG_SECTION][WINDOW_TITLE_KEY]
debug = config[COMMON_CONFIG_SECTION].getboolean(DEBUG_KEY)
debug_browser = config[COMMON_CONFIG_SECTION].getboolean(DEBUG_BROWSER_KEY)
debug_print = config[COMMON_CONFIG_SECTION].getboolean(DEBUG_PRINT_KEY)
debug_print_level = config[COMMON_CONFIG_SECTION][DEBUG_PRINT_LEVEL_KEY]
debug_html = config[COMMON_CONFIG_SECTION].getboolean(DEBUG_HTML_KEY)
ui = config[COMMON_CONFIG_SECTION].getboolean(UI_KEY)
use_api = config[COMMON_CONFIG_SECTION].getboolean(USE_API_KEY)
# TODO : Separate into different social config
consumer_key = config[TWITTER_CONFIG_SECTION][CONSUMER_KEY]
consumer_secret = config[TWITTER_CONFIG_SECTION][CONSUMER_SECRET]
access_token_key = config[TWITTER_CONFIG_SECTION][ACCESS_TOKEN_KEY]
access_token_secret = config[TWITTER_CONFIG_SECTION][ACCESS_TOKEN_SECRET]
number_of_tweets = config[TWITTER_CONFIG_SECTION][NUMBER_OF_TWEETS_KEY]
status_link = config[TWITTER_CONFIG_SECTION][STATUS_LINK_KEY]
open_status_link = config[TWITTER_CONFIG_SECTION][OPEN_STATUS_LINK_KEY]
search_url = config[TWITTER_CONFIG_SECTION][SEARCH_URL_KEY]
twitter_ids = [twitter_id.strip() for twitter_id in config[TWITTER_CONFIG_SECTION][TWITTER_IDS_KEY].split(",")]
debug_browser_view_url = config[TWITTER_CONFIG_SECTION][DEBUG_BROWSER_VIEW_URL_KEY]
debug_json = config[TWITTER_CONFIG_SECTION].getboolean(DEBUG_JSON_KEY)
next_page_key = config[TWITTER_CONFIG_SECTION][NEXT_PAGE_KEY]

current_debug_print_level = int(DebugPrintLevel[debug_print_level])
current_debug_print = debug_print
