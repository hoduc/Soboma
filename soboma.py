import requests
import configparser
import datetime
import sys
import traceback
import twitter
import json
from pin import Pin
from dateutil.parser import parse
from dateutil import tz
from datetime import datetime
from timeit import default_timer as timer
from enum import IntEnum
from operator import itemgetter
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from collections import OrderedDict
from PyQt5.QtWidgets import QApplication, QWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QSizePolicy, QLabel, QPushButton, QMainWindow, QFrame
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QRunnable, QObject, QThreadPool, QUrl, QSize, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PIL import Image
from PIL.ImageQt import ImageQt


UA = UserAgent()
HEADER = {'User-Agent' : str(UA.chrome) }
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

class DebugPrintLevel(IntEnum):
    DEBUG = 1
    INFO = 2
    WARN = 3
    ERROR = 4


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
twitter_ids = config[TWITTER_CONFIG_SECTION][TWITTER_IDS_KEY].split(",")
debug_browser_view_url = config[TWITTER_CONFIG_SECTION][DEBUG_BROWSER_VIEW_URL_KEY]

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
    def __init__(self, index, url, img_cache):
        super(DownloadImgRunnable, self).__init__()
        self.index, self.url = index, url
        self.img_cache = img_cache
        self.runnable_signal = RunnableSignal()

    def run(self):
        dbgp(("about to run Runnable:", self.index, self.url))
        q_img = None
        if self.url in self.img_cache:
            dbgp("{} in cache !!!".format(self.url))
            q_img = self.img_cache[self.url]
        else:
            downloaded_img = Image.open(requests.get(self.url, stream=True).raw)

            # to avoid gc-ed ?
            # https://stackoverflow.com/questions/61354609/pyqt5-setpixmap-crashing-when-trying-to-show-image-in-label
            q_img = QImage(ImageQt(downloaded_img).copy())
            self.img_cache[self.url] = q_img
            dbgp(("finished:", self.index, self.url, q_img))
        self.runnable_signal.done.emit(self.index, q_img)


class DownloadImgThreadPool(QObject):
    def __init__(self, meta_urls, ui_update_delegate):
        super(DownloadImgThreadPool, self).__init__()
        self.pool = QThreadPool.globalInstance()
        self.meta_urls = meta_urls
        self.img_cache = {}
        # TODO: Better way for passing these delegate and
        # the dependencies of meta_url
        # having index in it
        self.ui_update_delegate = ui_update_delegate

    def start(self):
        start = timer()
        dbgp("starting threadpool")
        for (index, url) in self.meta_urls:
            download_img_thread = DownloadImgRunnable(index, url, self.img_cache)
            # connect
            download_img_thread.runnable_signal.done[int, QImage].connect(self.ui_update_delegate)
            self.pool.start(download_img_thread)
        self.pool.waitForDone()
        end = timer()
        dbgpi("Thread pool taken {} seconds".format(str(end-start)))
        dbgp("Finished Threadpool")

def href_word(word, content = ""):
    if content == "":
        content = word
    return "<a href=\"{}\">{}</a>".format(word, content) if word and word.startswith("http") else word

# find and replace all link into href
def wrap_text_href(text):
    s = ""
    word = ""
    i = 0
    while i < len(text):
        while i < len(text) and (text[i] == " " or text[i] == "\n"):
            s += text[i]
            i += 1
        while i < len(text) and text[i] != " " and text[i] != "\n":
            word += text[i]
            i += 1
        # either found word
        s += href_word(word)
        word = ""
    s += href_word(word)
    return s

# to local time
def convert_dt(date_str):
    return datetime.strftime(parse(date_str).replace(tzinfo=tz.tzutc()).astimezone(tz=tz.tzlocal()),'%Y-%m-%d %H:%M:%S')


# TODO: Code clean up
class ResizableLabelImg(QLabel):
    def __init__(self, pixmap = None, parent = None):
        QLabel.__init__(self, parent)
        self.pixmap = pixmap

    def setPixmap(self, pixmap):
        self.pixmap = pixmap
        self.scaleLabelImg()

    def heightForWidth(self, width):
        return self.height() if not self.pixmap else self.pixmap.height()/self.pixmap.width()

    def sizeHint(self):
        return QSize(self.width(), self.heightForWidth(self.width()))

    def scaleLabelImg(self):
        if self.pixmap:
            super().setPixmap(self.pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event):
        self.scaleLabelImg()


class MediaPlayer(QWidget):
    def __init__(self, media_video_url, parent = None):
        super(MediaPlayer, self).__init__(parent)
        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        video_widget = QVideoWidget()
        layout = QVBoxLayout()
        layout.addWidget(video_widget)
        self.setLayout(layout)
        self.media_player.setMedia(QMediaContent(QUrl(media_video_url)))
        self.media_player.setVideoOutput(video_widget)
        self.media_player.play()



class MainWindow(QMainWindow):
    window_widget = None
    window_widget_layout = None
    main_widget = None
    layout = None
    debug_browser_layout = None
    def __init__(self, app, dtos):
        super(MainWindow, self).__init__()
        self.app = app # pass app just in case need to do some events
        self.dtos = dtos
        self.img_labels = []
        self.init_ui()

    def init_ui(self):
        self.scroll_area = QScrollArea()
        self.window_widget = QWidget()
        self.window_widget_layout = QHBoxLayout()
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
                profile_label = QLabel(bio + location + profile_stats_text)
                profile_label.setWordWrap(True)
                profile_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
                profile_img_label = QLabel()
                img_urls.append((0,profile_url))
                self.img_labels.append(profile_img_label)
                post_layout = QHBoxLayout()
                post_layout.addWidget(profile_img_label)
                post_layout.addWidget(profile_label)
                post_layout.addStretch(1)
                self.layout.addLayout(post_layout, 1)
            # TODO: Refactor this. Getting unwiedly pretty fast
            for act in activities:
                post_layout = QHBoxLayout()
                rep_author_img_url = None
                tweet, ts = act.content, act.created_at
                author, author_img_url, urls, medias = act.profile_name, act.profile_url, act.urls, act.media_urls
                tweet_text = wrap_text_href(tweet) + "\n...at " + convert_dt(ts) + "\n"
                dbgp(("Got urls:", urls))
                tweet_text += "\n".join(href_word(url, open_status_link) for url in urls)
                dbgp("final text:{}".format(tweet_text))
                tweet_author_label_img = QLabel()
                img_urls.append((len(img_urls), author_img_url))
                self.img_labels.append(tweet_author_label_img)
                post_layout.addWidget(tweet_author_label_img)
                # the tweet
                tweet_layout = QVBoxLayout()
                tweet_label = QLabel(tweet_text)
                tweet_label.setTextFormat(Qt.RichText)
                tweet_label.setScaledContents(True)
                tweet_label.setWordWrap(True)
                tweet_label.setOpenExternalLinks(True)
                tweet_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
                tweet_layout.addWidget(tweet_label)
                if medias:
                    for media in medias:
                        media_type, media_url = media[0], media[1]
                        if media_type == "video":
                            # IN ORDER FOR THIS TO WORK
                            # Download these filter in windows:
                            # https://github.com/Nevcairiel/LAVFilters/releases
                            media_video_url = media[-1]
                            dbgp("video {}".format(media_video_url))
                            tweet_layout.addWidget(MediaPlayer(media_video_url))
                        else:
                            media_attachement_label = ResizableLabelImg()
                            media_attachement_label.setScaledContents(True)
                            img_urls.append((len(img_urls), media_url))
                            self.img_labels.append(media_attachement_label)
                            tweet_layout.addWidget(media_attachement_label)
                post_layout.addLayout(tweet_layout)
                post_layout.addStretch(1)
                # add to parent layout
                self.layout.addLayout(post_layout, 1)
        self.main_widget.setLayout(self.layout)
        # TODO: scroll on the left widget
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameStyle(QFrame.NoFrame)
        self.scroll_area.setWidget(self.main_widget)
        if debug_browser:
            twitter_web_view = QWebEngineView()
            twitter_web_view.load(QUrl(debug_browser_view_url.format(twitter_id)))
            self.debug_browser_layout = QVBoxLayout()
            self.debug_browser_layout.addWidget(twitter_web_view)
            self.window_widget_layout.addLayout(self.debug_browser_layout)

        self.window_widget_layout.addWidget(self.scroll_area)
        self.window_widget.setLayout(self.window_widget_layout)
        self.setCentralWidget(self.window_widget)
        self.setWindowTitle(window_title)
        # start background worker thread
        self.download_img_thread_pool = DownloadImgThreadPool(img_urls, self.update_img_label)
        self.download_img_thread_pool.start()

    def update_img_label(self, label_index, q_img):
        dbgp(("updating :", label_index, q_img))
        img_label = self.img_labels[label_index]
        img_label.setPixmap(QPixmap.fromImage(q_img))



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
    # TODO: Should consider this as part of activities?
    profile_img = user.profile_image_url
    profile_bio = user.description
    profile_location = user.location
    profile_stats = [user.statuses_count, user.friends_count, user.followers_count]
    profile_elem = (profile_img, profile_stats, profile_bio, profile_location)
    dbgp(user)
    # activities
    acts = []
    # TODO : Get all tweets for days
    timeline = api.GetUserTimeline(screen_name=twitter_id, count=number_of_tweets)
    tweets = []
    for tweet in timeline:
        tweets.append(str(tweet))
        dbgp(tweet)
        replies = ()
        author = () # (screen_name, profile_image_url)
        # favor whatever url it has
        urls = None
        medias = None
        profile_name = ""
        profile_url = ""
        created_at = tweet.created_at
        relations = []
        if tweet.retweeted_status: # retweet has to pull different stuff
            dbgp("Retweeting")
            rt = tweet.retweeted_status
            profile_name = tweet.user.screen_name
            profile_url = rt.user.profile_image_url
            medias = rt.media
            # TODO: medias on all these
        else:
            dbgp("Not Retweeting")
            profile_name = tweet.user.screen_name
            profile_url = tweet.user.profile_image_url
            medias = tweet.media

        urls = [status_link.format(profile_name, tweet.id)]
        media_urls = []
        if medias:
            for media in medias:
                media_url = [media.type, media.media_url]
                media_url.append(media.media_url)
                if media.type == "video":
                    video_url = media.video_info["variants"][-1]["url"]
                    dbgp("video {}".format(video_url))
                    media_url.append(video_url)
                media_urls.append(media_url)
        content = "@" + profile_name
        if tweet.in_reply_to_screen_name: # not replying to self
            dbgp("Replying to {}".format(tweet.in_reply_to_screen_name))
            content += " replies to @" + tweet.in_reply_to_screen_name
            if not urls:
                dbgp("Reconstructing urls:")
                urls = [status_link.format(tweet.in_reply_to_screen_name, tweet.in_reply_to_status_id)]
        content += " : " + tweet.text
        dbgp(("final_urls:", urls))
        # TODO: relation
        acts.append(Pin(profile_name, profile_url, created_at, content, urls, media_urls))
    if debug:
        with open(twitter_id + ".json", "w") as json_file:
            json_dict = {}
            json_dict["profile_img"] = profile_img
            json_dict["profile_stats"] = profile_stats
            json_dict["profile_bio"] = profile_bio
            json_dict["profile_location"] = profile_location
            json_dict["tweets"] = tweets
            json.dump(json_dict, json_file, indent=4)
    dtos[twitter_id] = (profile_elem, acts)
    dbgpi("Finished getting tweets for {}".format(twitter_id))
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
        dbgp(dtos[twitter_id])


    if ui:
        app = QApplication([])
        window = MainWindow(app, dtos)
        window.show()
        sys.exit(app.exec_())
