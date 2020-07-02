import requests
import configparser
import datetime
import sys
import traceback
import twitter
from enum import IntEnum
from operator import itemgetter
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from collections import OrderedDict
from PyQt5.QtWidgets import QApplication, QWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QLabel, QMainWindow
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QRunnable, QObject, QThreadPool, pyqtSignal
from PIL import Image
from PIL.ImageQt import ImageQt


UA = UserAgent()
HEADER = {'User-Agent' : str(UA.chrome) }
CONFIG_FILE_NAME = "config"
TWITTER_CONFIG_SECTION = "twitter"
CONSUMER_KEY = "consumer_key"
CONSUMER_SECRET = "consumer_secret"
ACCESS_TOKEN_KEY = "access_token_key"
ACCESS_TOKEN_SECRET = "access_token_secret"
USE_API_KEY = "use_api"
SEARCH_URL_KEY = "search_url"
TWITTER_IDS_KEY = "twitter_ids"
UI_KEY = "ui"
DEBUG_KEY = "debug"
DEBUG_PRINT_KEY = "debug_print"
DEBUG_HTML_KEY = "debug_html"
DEBUG_PRINT_LEVEL_KEY = "debug_print_level"

class DebugPrintLevel(IntEnum):
    DEBUG = 1
    INFO = 2
    WARN = 3
    ERROR = 4

twitter_config = configparser.ConfigParser()
twitter_config.read(CONFIG_FILE_NAME)
consumer_key = twitter_config[TWITTER_CONFIG_SECTION][CONSUMER_KEY]
consumer_secret = twitter_config[TWITTER_CONFIG_SECTION][CONSUMER_SECRET]
access_token_key = twitter_config[TWITTER_CONFIG_SECTION][ACCESS_TOKEN_KEY]
access_token_secret = twitter_config[TWITTER_CONFIG_SECTION][ACCESS_TOKEN_SECRET]
use_api = twitter_config[TWITTER_CONFIG_SECTION].getboolean(USE_API_KEY)
search_url = twitter_config[TWITTER_CONFIG_SECTION][SEARCH_URL_KEY]
twitter_ids = twitter_config[TWITTER_CONFIG_SECTION][TWITTER_IDS_KEY].split(",")
ui = twitter_config[TWITTER_CONFIG_SECTION].getboolean(UI_KEY)
debug = twitter_config[TWITTER_CONFIG_SECTION].getboolean(DEBUG_KEY)
debug_print = twitter_config[TWITTER_CONFIG_SECTION].getboolean(DEBUG_PRINT_KEY)
debug_print_level = twitter_config[TWITTER_CONFIG_SECTION][DEBUG_PRINT_LEVEL_KEY]
debug_html = twitter_config[TWITTER_CONFIG_SECTION].getboolean(DEBUG_HTML_KEY)

def dbg_print(msg, debug_print_level, should_print = True):
    if should_print:
        print("{} {}".format("[" + debug_print_level + "]", msg))

def dbgp_helper(msg, debug_log_level):
    dbg_print(msg, debug_log_level.name, debug_print and int(DebugPrintLevel[debug_print_level]) <= int(debug_log_level))

def dbgp(msg):
    dbgp_helper(msg, DebugPrintLevel.DEBUG)

def dbgpi(msg):
    dbgp_helper(msg, DebugPrintLevel.INFO)

def dbgpw(msg):
    dbgp_helper(msg, DebugPrintLevel.WARN)

def dbgpe(msg):
    dbgp_helper(msg, DebugPrintLevel.ERROR)

class RunnableSignal(QObject):
    done = pyqtSignal(int, QImage)

class DownloadImgRunnable(QRunnable):
    def __init__(self, index, url):
        super(DownloadImgRunnable, self).__init__()
        self.index, self.url = index, url
        self.runnable_signal = RunnableSignal()

    def run(self):
        dbgp(("about to run Runnable:", self.index, self.url))
        downloaded_img = Image.open(requests.get(self.url, stream=True).raw)

        # to avoid gc-ed ?
        # https://stackoverflow.com/questions/61354609/pyqt5-setpixmap-crashing-when-trying-to-show-image-in-label
        q_img = QImage(ImageQt(downloaded_img).copy())
        dbgp(("finished:", self.index, self.url, q_img))
        self.runnable_signal.done.emit(self.index, q_img)


class DownloadImgThreadPool(QObject):
    def __init__(self, meta_urls, ui_update_delegate):
        super(DownloadImgThreadPool, self).__init__()
        self.pool = QThreadPool.globalInstance()
        self.meta_urls = meta_urls
        self.ui_update_delegate = ui_update_delegate

    def start(self):
        dbgp("starting threadpool")
        for (index, url) in self.meta_urls:
            download_img_thread = DownloadImgRunnable(index, url)
            # connect
            download_img_thread.runnable_signal.done[int, QImage].connect(self.ui_update_delegate)
            self.pool.start(download_img_thread)
        self.pool.waitForDone()


class MainWindow(QMainWindow):
    main_widget = None
    layout = None
    def __init__(self, app, dtos):
        super(MainWindow, self).__init__()
        self.app = app # pass app just in case need to do some events
        self.dtos = dtos
        self.img_labels = []
        self.init_ui()

    def init_ui(self):
        self.scroll_area = QScrollArea()
        self.main_widget = QWidget()
        self.layout = QVBoxLayout()
        self.layout.addStretch(1)
        img_urls = []
        for twitter_id in self.dtos:
            profile_elem, activities = self.dtos[twitter_id]
            if profile_elem:
                profile_url, profile_stats, bio, location = profile_elem
                # TODO: These if and default values
                location = "" if not location else location.strip() + "\n"
                bio = "" if not bio else bio.strip() + "\n"

                profile_mapping = ["Tweets", "Following", "Followers"]
                profile_stats_text = ""
                for (i, stat) in enumerate(profile_stats):
                    profile_stats_text += "{} {},".format(stat, profile_mapping[i])
                if profile_stats_text:
                    profile_stats_text = profile_stats_text[:-1] + "\n"
                profile_label = QLabel(location + bio + profile_stats_text)
                profile_label.setWordWrap(True)
                profile_img_label = QLabel()
                img_urls.append((0,profile_url))
                self.img_labels.append(profile_img_label)
                self.layout.addWidget(profile_label)
                self.layout.addWidget(profile_img_label)
            for (tweet, ts, replies) in activities:
                post_layout = QHBoxLayout()
                rep_author_img_url = None
                dbgp((tweet, ts, replies))
                author, author_img_url = replies[0] # always has sth
                tweet_text = "@" + author
                if len(replies) > 1: # real replies
                    tweet_text += " replies to " + ",".join("@" + tid for tid in replies[1:]) + " : "
                else: # author post
                    tweet_text += " : "
                tweet_text += tweet + "\n...at " + ts
                tweet_author_label_img = QLabel()
                img_urls.append((len(img_urls), author_img_url))
                self.img_labels.append(tweet_author_label_img)
                post_layout.addWidget(tweet_author_label_img)
                # the tweet
                tweet_label = QLabel(tweet_text)
                tweet_label.setScaledContents(True)
                tweet_label.setWordWrap(True)
                post_layout.addWidget(tweet_label)
                post_layout.addStretch(1)
                # add to parent layout
                self.layout.addLayout(post_layout)
        self.main_widget.setLayout(self.layout)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.main_widget)
        self.setCentralWidget(self.scroll_area)
        self.setWindowTitle("Soboma")
        # start background worker thread
        self.download_img_thread_pool = DownloadImgThreadPool(img_urls, self.update_img_label)
        self.download_img_thread_pool.start()

    def update_img_label(self, label_index, q_img):
        dbgp(("updating :", label_index, q_img))
        self.img_labels[label_index].setPixmap(QPixmap.fromImage(q_img))



def parse_html(html_doc, dtos, page, twitter_id):
    soup = BeautifulSoup(html_doc, 'html.parser')
    activities = []
    profile_elem = None
    if page == 0:
        profile_li = soup.find("li", class_ = "AdaptiveStreamUserGallery")
        if profile_li:
            dbgp(profile_li)
            profile_img = profile_li.find("img", class_ = "ProfileCard-avatarImage")
            if profile_img:
                profile_img = profile_img["src"]
            #[tweets, followings, followers]
            profile_stats = ["".join(elem.get_text().split()) for elem in profile_li.find_all("span", class_ = "ProfileCardStats-statValue")]
            # TODO: is there an elvis operator in python?
            profile_bio = profile_li.find("p", class_ = "ProfileCard-bio")
            # TODO: These if and default values
            if profile_bio:
                profile_bio = profile_bio.get_text()
            profile_location = profile_li.find("p", class_ = "ProfileCard-locationAndUrl")
            if profile_location:
                profile_location = profile_location.get_text()
            profile_elem = (profile_img, profile_stats, profile_bio, profile_location)
        dtos[twitter_id] = (profile_elem, activities)
        dbgp(profile_elem)
    lis = soup.find_all("li", class_ = "js-stream-item")
    for li in lis:
        dbgp(li)
        ts = -1
        tweet = li.find("p", class_ = "TweetTextSize")
        if tweet:
            tweet = tweet.get_text()
            ts = li.find("span", class_ = "_timestamp")
            if ts:
                ts = datetime.datetime.fromtimestamp(float(ts["data-time-ms"])/1000).strftime("%Y-%m-%d %H:%M:%S")
        if not tweet or ts == -1:
            continue
        dbgp(("tweet:", tweet))
        r = ()
        account_group = li.find("a", class_ = "account-group")
        author_img = account_group.find("img", class_ = "avatar")
        r = r + ((account_group['href'][1:],author_img['src']),)
        replies = li.find("div", class_ = "ReplyingToContextBelowAuthor")
        if replies:
            for a in replies.find_all('a'):
                r = r + (a['href'][1:],)
        activities.append((tweet, ts, r))
        if page > 0:
            dtos[twitter_id] = (dtos[twitter_id][0], dtos[twitter_id][1] + activities)
    return dtos, soup

def get_tweets(twitter_id, dtos):
    page, marker = 0, None
    while True:
        twitter_id_html = twitter_id + "_" + str(page) + ".html"
        html_doc = ""
        try:
            soup = None
            if debug_html:
                with open(twitter_id_html, "r", encoding = "utf-8") as html_file:
                    html_doc = html_file.read()
                dtos, soup = parse_html(html_doc, dtos, page, twitter_id)
                page += 1
                continue
            url = search_url + twitter_id
            if page == 0:
                url += "&min_position=0"
            if marker:
                dbgp("marker = " + marker)
                url += "&max_position=" + marker
            dbgp(('url=', url))
            r = requests.get(url, headers=HEADER)
            if r.status_code == 200:
                json = r.json()
                html_doc = json['items_html']
                if 'max_position' in json:
                    marker = json['max_position']
                dbgp("marker = " + marker)
                dtos, soup = parse_html(html_doc, dtos, page, twitter_id)
                if debug:
                    with open(twitter_id_html, "w", encoding = "utf-8") as html_file:
                        html_file.write(soup.prettify())
                if not json['has_more_items']:
                    break
            else:
                dbgp("Got status:", r.status_code)
                dbgp(r)
        except:
            dbgpe("ERROR {} : {}".format(twitter_id, sys.exc_info()[0]))
            dbgpe(traceback.format_exc())
            soup = BeautifulSoup(html_doc, 'html.parser')
            with open(twitter_id_html, "w", encoding = "utf-8") as html_file:
                html_file.write(soup.prettify())
                sys.exit(-1)
        page += 1
    return dtos

def get_tweets_api(twitter_id, dtos, api):
    dbgpi("Getting tweets for {}".format(twitter_id))
    # get profile contents
    profile_elem = None
    user = api.GetUser(screen_name=twitter_id)
    profile_img = user.profile_image_url
    profile_bio = user.description
    profile_location = user.location
    profile_stats = [user.statuses_count, user.friends_count, user.followers_count]
    profile_elem = (profile_img, profile_stats, profile_bio, profile_location)
    dbgp(user)
    # activities
    activities = []
    timeline = api.GetUserTimeline(screen_name=twitter_id, count=20)
    for tweet in timeline:
        dbgp(tweet)
        replies = ((tweet.user.screen_name, tweet.user.profile_image_url), )
        if tweet.in_reply_to_screen_name:
            replies = replies + (tweet.in_reply_to_screen_name, )
        activities.append((tweet.text, tweet.created_at, replies))
    dtos[twitter_id] = (profile_elem, activities)
    dbgp("Finished getting tweets for {}".format(twitter_id))
    return dtos

if __name__ == "__main__":
    dtos = OrderedDict()
    api = None if not use_api else twitter.Api(consumer_key=consumer_key,
                  consumer_secret=consumer_secret,
                  access_token_key=access_token_key,
                  access_token_secret=access_token_secret)
    for twitter_id in twitter_ids:
        if not use_api:
            dtos = get_tweets(twitter_id, dtos)
        else:
            dtos = get_tweets_api(twitter_id, dtos, api)
        # sorted(dtos[twitter_id][1], key = itemgetter(1))
        dbgpi(dtos[twitter_id])


    if ui:
        app = QApplication([])
        window = MainWindow(app, dtos)
        window.show()
        sys.exit(app.exec_())









