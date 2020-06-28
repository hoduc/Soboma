import requests
import configparser
import datetime
import sys
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from collections import OrderedDict
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMainWindow
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import QRunnable, QObject, QThreadPool, pyqtSignal
from PIL import Image
from PIL.ImageQt import ImageQt


UA = UserAgent()
HEADER = {'User-Agent' : str(UA.chrome) }
CONFIG_FILE_NAME = "config"
TWITTER_CONFIG_SECTION = "twitter"
SEARCH_URL_KEY = "search_url"
TWITTER_IDS_KEY = "twitter_ids"
UI_KEY = "ui"
DEBUG_KEY = "debug"
DEBUG_PRINT_KEY = "debug_print"
DEBUG_PRINT_LEVEL_KEY = "debug_print_level"
DEBUG_PRINT_LEVEL_INFO = "INFO"
DEBUG_PRINT_LEVEL_DEBUG = "DEBUG"
DEBUG_PRINT_LEVEL_ERROR = "ERROR"
DEBUG_PRINT_LEVEL_WARN = "WARN"

twitter_config = configparser.ConfigParser()
twitter_config.read(CONFIG_FILE_NAME)
search_url = twitter_config[TWITTER_CONFIG_SECTION][SEARCH_URL_KEY]
twitter_ids = twitter_config[TWITTER_CONFIG_SECTION][TWITTER_IDS_KEY].split(",")
ui = twitter_config[TWITTER_CONFIG_SECTION].getboolean(UI_KEY)

debug = twitter_config[TWITTER_CONFIG_SECTION].getboolean(DEBUG_KEY)
debug_print = twitter_config[TWITTER_CONFIG_SECTION].getboolean(DEBUG_PRINT_KEY)
debug_print_level = twitter_config[TWITTER_CONFIG_SECTION][DEBUG_PRINT_LEVEL_KEY]

def dbg_print(msg, debug_print_level, should_print = True):
    if should_print:
        print("{} {}".format("[" + debug_print_level + "]", msg))

def dbgp_helper(msg, debug_log_level):
    dbg_print(msg, debug_print_level, debug_print and  debug_print_level == debug_log_level)

def dbgp(msg):
    dbgp_helper(msg, DEBUG_PRINT_LEVEL_DEBUG)

def dbgpi(msg):
    dbgp_helper(msg,  DEBUG_PRINT_LEVEL_INFO)

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
        self.main_widget = QWidget()
        self.layout = QVBoxLayout()
        self.layout.addStretch(1)
        img_urls = []
        for twitter_id in self.dtos:
            profile_elem, activities = self.dtos[twitter_id]
            profile_url, profile_stats, bio, location = profile_elem
            # TODO: These if and default values
            if not location:
                location = ""
            location = "" if not location else "".join(location.split()) + "\n"
            profile_label = QLabel(location + bio + ",".join(profile_stats))
            profile_img_label = QLabel()
            img_urls.append((0,profile_url))
            self.img_labels.append(profile_img_label)
            self.layout.addWidget(profile_label)
            self.layout.addWidget(profile_img_label)
            for (tweet, ts, replies) in activities:
                post_layout = QHBoxLayout()
                rep_author_img_url = None
                dbgpi((tweet, ts, replies))
                author, author_img_url = replies[0] # always has sth
                tweet_text = "@" + author
                if len(replies) > 1: # real replies
                    tweet_text += " replies to " + ",".join("@" + tid for tid in replies[1:]) + " : "
                else: # author post
                    tweet_text += " : "
                tweet_text += tweet + "\n...at " + datetime.datetime.fromtimestamp(float(ts)/1000).strftime("%Y-%m-%d %H:%M:%S")
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
        self.setCentralWidget(self.main_widget)
        # start background worker thread
        self.download_img_thread_pool = DownloadImgThreadPool(img_urls, self.update_img_label)
        self.download_img_thread_pool.start()

    def update_img_label(self, label_index, q_img):
        dbgp(("updating :", label_index, q_img))
        self.img_labels[label_index].setPixmap(QPixmap.fromImage(q_img))



if __name__ == "__main__":
    dtos = OrderedDict()
    for twitter_id in twitter_ids:
        dbgp(('url=', search_url + twitter_id))
        r = requests.get(search_url + twitter_id, headers=HEADER)
        if r.status_code == 200:
            json = r.json()
            html_doc = json['items_html']
            soup = BeautifulSoup(html_doc, 'html.parser')
            profile_li = soup.find("li", class_ = "AdaptiveStreamUserGallery")
            profile_img = profile_li.find("img", class_ = "ProfileCard-avatarImage")["src"]
            #[tweets, followings, followers]
            profile_stats = ["".join(elem.get_text().split()) for elem in profile_li.find_all("span", class_ = "ProfileCardStats-stat")]
            # TODO: is there an elvis operator in python?
            profile_bio = profile_li.find("p", class_ = "ProfileCard-bio")
            # TODO: These if and default values
            if profile_bio:
                profile_bio = profile_bio.get_text()
            profile_location = profile_li.find("p", class_ = "ProfileCard-locationAndUrl")
            if profile_location:
                profile_location = profile_location.get_text()
            profile_elem = (profile_img, profile_stats, profile_bio, profile_location)
            activities = []
            lis = soup.find_all("li", class_ = "js-stream-item")
            for li in lis:
                dbgp(li)
                ts = -1
                tweet = li.find("p", class_ = "TweetTextSize")
                if tweet:
                    tweet = tweet.get_text()
                    ts = li.find("span", class_ = "_timestamp")
                    if ts:
                        ts = ts["data-time-ms"]
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
            dbgp(activities)
            dbgp(profile_elem)
            dtos[twitter_id] = (profile_elem, activities)
            if debug:
                with open(twitter_id + ".html", "w", encoding = "utf-8") as html_file:
                    html_file.write(soup.prettify())
        else:
            print("Got status:", r.status_code)
            print(r)

    if ui:
        app = QApplication([])
        window = MainWindow(app, dtos)
        window.show()
        sys.exit(app.exec_())









