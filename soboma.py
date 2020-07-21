import requests
import configparser
import datetime
import sys
import traceback
import twitter
import json
import dataclasses
from pin import Pin
from util import DebugPrintLevel, current_debug_print_level, current_debug_print, dbgp, dbgpi, dbgpw, dbgpe
from config import *
from timeit import default_timer as timer
from enum import IntEnum
from operator import itemgetter
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from collections import OrderedDict
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QWidget, QStackedWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QSizePolicy, QLabel, QMainWindow, QFrame
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QRunnable, QObject, QThreadPool, QUrl, QSize, QPoint, QByteArray, QBuffer, QIODevice, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PIL import Image
from PIL.ImageQt import ImageQt
from ui import PinWidget


class DownloadImgRunnable(QRunnable):
    class RunnableSignal(QObject):
        done = pyqtSignal(QPixmap)

    def __init__(self, url, img_cache):
        super(DownloadImgRunnable, self).__init__()
        self.url = url
        self.img_cache = img_cache
        self.runnable_signal = self.RunnableSignal()

    def run(self):
        dbgp(("about to run Runnable:", self.url))
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
            dbgp(("finished:", self.url))
        self.runnable_signal.done.emit(QPixmap.fromImage(q_img))


class DownloadImgThreadPool(QObject):
    def __init__(self):
        super(DownloadImgThreadPool, self).__init__()
        self.pool = QThreadPool.globalInstance()
        self.download_img_runnables = []
        self.img_cache = {}

    def start(self):
        start = timer()
        dbgp("starting threadpool")
        for download_img_runnable in self.download_img_runnables:
            self.pool.start(download_img_runnable)
        self.pool.waitForDone()
        end = timer()
        self.download_img_runnables = []
        dbgpi("Thread pool taken {} seconds".format(str(end-start)))
        dbgp("Finished Threadpool")

    def register_img_url(self, img_url, ui_update_delegate):
        download_img_runnable = DownloadImgRunnable(img_url, self.img_cache)
        download_img_runnable.runnable_signal.done[QPixmap].connect(ui_update_delegate)
        self.download_img_runnables.append(download_img_runnable)


class MainWidget(QWidget):
    def __init__(self, twitter_id, activities):
        super(MainWidget, self).__init__()
        self.twitter_id = twitter_id
        self.activities = activities
        self.img_labels = []
        self.download_img_thread_pool = DownloadImgThreadPool()
        self.init_ui()

    def init_ui(self):
        self.window_widget_layout = QHBoxLayout()
        self.setLayout(self.window_widget_layout)
        self.main_widget_layout = QVBoxLayout()
        self.main_widget_layout.addStretch(1)
        self.main_widget = QWidget()
        self.main_widget.setLayout(self.main_widget_layout)
        self.scroll_area = QScrollArea()
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameStyle(QFrame.NoFrame)
        self.scroll_area.setWidget(self.main_widget)
        self.window_widget_layout.addWidget(self.scroll_area)
        for act in self.activities:
            self.main_widget_layout.addWidget(PinWidget(act,self.download_img_thread_pool))
        if debug_browser:
            self.twitter_web_view = QWebEngineView()
            self.twitter_web_view.load(QUrl(debug_browser_view_url.format(self.twitter_id)))
            dbgp("open browser for {} with title {}".format(self.twitter_id, self.twitter_web_view.title()))
            self.debug_browser_layout = QVBoxLayout()
            self.debug_browser_layout.addWidget(self.twitter_web_view)
            self.window_widget_layout.addLayout(self.debug_browser_layout)
        self.download_img_thread_pool.start()

class MainWindow(QMainWindow):
    def __init__(self, app, dtos):
        super(MainWindow, self).__init__()
        self.app = app # pass app just in case need to do some events
        self.twitter_ids = list(dtos.keys())
        dbgp("twitter_ids:{} => {}".format(dtos.keys(), self.twitter_ids))
        self.stack_widget = QStackedWidget()
        for twitter_id in dtos:
            profile_elem, activities = dtos[twitter_id]
            self.stack_widget.addWidget(MainWidget(twitter_id, activities))
        self.stack_widget.keyPressEvent = self.changePage
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.stack_widget)
        self.setCentralWidget(self.stack_widget)
        self.setWindowTitle(window_title)

    def changePage(self, event):
        if event.key() == ord(next_page_key):
            next_index = (self.stack_widget.currentIndex() + 1) % self.stack_widget.count()
            dbgp("Changing to show the content of twitter_id :{}:".format(self.twitter_ids[next_index]))
            self.stack_widget.setCurrentIndex((next_index))



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

def default_str_new_line(s):
    return "" if not s else s.strip() + "\n"

def profile(user):
    dbgp(user)
    profile_img = user.profile_image_url
    profile_bg_img = user.profile_banner_url
    profile_bio = default_str_new_line(user.description)
    profile_location = default_str_new_line(user.location)
    profile_stats = [user.statuses_count, user.friends_count, user.followers_count]
    profile_mapping = ["Tweets", "Following", "Followers"]
    profile_stats_text = ""
    for (i, stat) in enumerate(profile_stats):
        profile_stats_text += "{} {},".format(stat, profile_mapping[i])
    if profile_stats_text:
        profile_stats_text = profile_stats_text[:-1] + "\n"
    profile_elem = (profile_img, profile_bg_img, profile_stats, profile_bio, profile_location)
    content = profile_bio + profile_location + profile_stats_text
    return profile_elem, Pin(profile_url = profile_img, content = content)


def get_tweets_api(twitter_id, dtos, api):
    dbgpi("Getting tweets for {}".format(twitter_id))
    # get profile contents
    profile_elem = None
    user = api.GetUser(screen_name=twitter_id)
    profile_elem, profile_pin = profile(user)
    profile_img, profile_bg_img, profile_stats, profile_bio, profile_location = profile_elem
    # activities
    # TODO: indicates profile in activities
    # Or always has profile at 0th index
    # and other activities for e.g next page
    # starting at 1th index
    acts = [profile_pin]
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
        elif tweet.quoted_status:
            dbgp("Quote status")
            qt = tweet.quoted_status
            profile_name = tweet.user.screen_name
            profile_url = qt.user.profile_image_url
            medias = qt.media
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
                # TODO: Confirm gif saved as mp4 ?
                if media.type == "video" or media.type == "animated_gif":
                    video_url = media.video_info["variants"][-1]["url"]
                    dbgp("video {}".format(video_url))
                    media_url = ["video", media.media_url, video_url]
                media_urls.append(media_url)
        content = "@" + profile_name
        if tweet.in_reply_to_screen_name: # not replying to self
            dbgp("Replying to {}".format(tweet.in_reply_to_screen_name))
            content += " replies to @" + tweet.in_reply_to_screen_name
            if not urls:
                dbgp("Reconstructing urls:")
                urls = [status_link.format(tweet.in_reply_to_screen_name, tweet.in_reply_to_status_id)]
        elif tweet.quoted_status: # TODO: Refactor these
            content += " (quoted @" + tweet.quoted_status.user.screen_name + ": \"" + tweet.quoted_status.text + "\")"
        content += " : " + tweet.text
        dbgp(("final_urls:", urls))
        # TODO: relation
        acts.append(Pin(profile_name, profile_url, created_at, content, urls, media_urls))
    if debug:
        with open(twitter_id + ".json", "w") as json_file:
            json_dict = {}
            json_dict["profile_img"] = profile_img
            json_dict["profile_bg_img"] = profile_bg_img
            json_dict["profile_stats"] = profile_stats
            json_dict["profile_bio"] = profile_bio
            json_dict["profile_location"] = profile_location
            json_dict["acts"] = [json.dumps(dataclasses.asdict(act)) for act in acts]
            json_dict["tweets"] = tweets
            json.dump(json_dict, json_file, indent=4)
    dtos[twitter_id] = (profile_elem, acts)
    dbgpi("Finished getting tweets for {}".format(twitter_id))
    return dtos

if __name__ == "__main__":
    dtos = OrderedDict()
    api = None if not use_api and not debug_json else twitter.Api(consumer_key=consumer_key,
                  consumer_secret=consumer_secret,
                  access_token_key=access_token_key,
                  access_token_secret=access_token_secret)
    for twitter_id in twitter_ids:
        if debug_json:
            dbgp("debug_json")
            twitter_id_json = twitter_id + ".json"
            if not Path(twitter_id_json).is_file():
                dbgp("{} does not exist!!!".format(twitter_id_json))
            else:
                with open(twitter_id_json, "r") as json_file:
                    json_dict = json.load(json_file)
                    # TODO: idiomatic way of deserialize json
                    # TODO : better way to write out debugs
                    acts = []
                    for act_str in json_dict["acts"]:
                        act = json.loads(act_str)
                        profile_name = act["profile_name"]
                        profile_url = act["profile_url"]
                        created_at = act["created_at"]
                        content = act["content"]
                        urls = act["urls"]
                        media_urls = act["media_urls"]
                        acts.append(Pin(profile_name, profile_url, created_at, content, urls, media_urls))
                    profile_elem = (json_dict["profile_img"], json_dict["profile_bg_img"], json_dict["profile_stats"], json_dict["profile_bio"], json_dict["profile_location"])
                    dtos[twitter_id] = (profile_elem, acts)
            continue

        if not use_api:
            dbgp("not user api")
            dtos = get_tweets(twitter_id, dtos)
        else:
            dbgp("use api")
            dtos = get_tweets_api(twitter_id, dtos, api)
        dbgp(dtos[twitter_id])


    if ui:
        app = QApplication([])
        window = MainWindow(app, dtos)
        window.show()
        sys.exit(app.exec_())
