import requests
import configparser
import datetime
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt5.QtGui import QPixmap
from PIL import Image, ImageQt


UA = UserAgent()
HEADER = {'User-Agent' : str(UA.chrome) }
CONFIG_FILE_NAME = "config"
TWITTER_CONFIG_SECTION = "twitter"
SEARCH_URL_KEY = "search_url"
TWITTER_IDS_KEY = "twitter_ids"
UI_KEY = "ui"
DEBUG_KEY = "debug"
DEBUG_PRINT_KEY = "debug_print"

twitter_config = configparser.ConfigParser()
twitter_config.read(CONFIG_FILE_NAME)
search_url = twitter_config[TWITTER_CONFIG_SECTION][SEARCH_URL_KEY]
twitter_ids = twitter_config[TWITTER_CONFIG_SECTION][TWITTER_IDS_KEY].split(",")
ui = twitter_config[TWITTER_CONFIG_SECTION].getboolean(UI_KEY)
debug = twitter_config[TWITTER_CONFIG_SECTION].getboolean(DEBUG_KEY)
debug_print = twitter_config[TWITTER_CONFIG_SECTION].getboolean(DEBUG_PRINT_KEY)

def dbg_print(msg, should_print = True):
    if should_print:
        print(msg)

def dbgp(msg):
    dbg_print(msg, debug_print)

def qpixmap_from_url(url):
    url_image = Image.open(requests.get(url, stream=True).raw)
    return QPixmap.fromImage(ImageQt.ImageQt(url_image))

if __name__ == "__main__":
    dtos = {}
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
            if profile_bio:
                profile_bio = profile_bio.get_text()
            profile_location = profile_li.find("p", class_ = "ProfileCard-locationAndUrl")
            if profile_location:
                profile_location = profile_location.get_text()
            profile_elem = (profile_img, profile_stats, profile_bio, profile_location)
            activities = []
            lis = soup.find_all("li", class_ = "js-stream-item")
            for li in lis:
                ts = -1
                tweet = li.find("p", class_ = "TweetTextSize")
                if tweet:
                    tweet = tweet.get_text()
                    ts = li.find("span", class_ = "_timestamp")
                    if ts:
                        ts = ts["data-time-ms"]
                dbgp(("tweet:", tweet))
                r = ()
                replies = li.find("div", class_ = "ReplyingToContextBelowAuthor")
                if replies:
                    # find author of the replies
                    # TODO: extract user_id to link
                    account_group = li.find("a", class_ = "account-group")
                    author_img = account_group.find("img", class_ = "avatar")
                    r = r + ((account_group['href'][1:],author_img['src']),)
                    for a in replies.find_all('a'):
                        r = r + (a['href'][1:],)
                if not tweet or ts == -1:
                    continue
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
        window = QWidget()
        layout = QVBoxLayout()
        for twitter_id in twitter_ids:
            # (url, stats, bio, location)
            # [(tweet, timestamp, (author, reply1, reply2,...))]
            profile_elem, activities = dtos[twitter_id]
            profile_url, profile_stats, bio, location = profile_elem
            profile_label = QLabel(str(location) + "\n" + bio + ",".join(profile_stats))
            profile_img_label = QLabel()
            profile_img_label.setPixmap(qpixmap_from_url(profile_url))
            layout.addWidget(profile_label)
            layout.addWidget(profile_img_label)
            for (tweet, ts, replies) in activities:
                replying_author_qpixmap = None
                dbgp((tweet, ts, replies))
                tweet_text = ""
                if replies:
                    replying_author, replying_author_img = replies[0]
                    tweet_text += "@" + replying_author + " replies to " + ",".join("@" + tid for tid in replies[1:])
                    replying_author_qpixmap = qpixmap_from_url(replying_author_img)
                tweet_text += "\n" + tweet + "...at " + datetime.datetime.fromtimestamp(float(ts)/1000).strftime("%Y-%m-%d %H:%M:%S")
                if replying_author_qpixmap:
                    tweet_reply_author_label_img = QLabel()
                    tweet_reply_author_label_img.setPixmap(replying_author_qpixmap)
                    layout.addWidget(tweet_reply_author_label_img)
                tweet_label = QLabel(tweet_text)
                layout.addWidget(tweet_label)

        window.setLayout(layout)
        window.show()
        app.exec_()









