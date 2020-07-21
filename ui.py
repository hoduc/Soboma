from datetime import datetime
from dateutil.parser import parse
from dateutil import tz
from util import dbgp, dbgpi, dbgpw, dbgpe
from config import open_status_link
from PyQt5.QtWidgets import QApplication, QWidget, QStackedWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QSizePolicy, QLabel, QMainWindow, QFrame
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QRunnable, QObject, QThreadPool, QUrl, QSize, QPoint, QByteArray, QBuffer, QIODevice, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEngineView

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

def href_word(word, content = ""):
    if content == "":
        content = word
    return "<a href=\"{}\">{}</a>".format(word, content) if word and word.startswith("http") else word

# to local time
def convert_dt(date_str):
    return datetime.strftime(parse(date_str).replace(tzinfo=tz.tzutc()).astimezone(tz=tz.tzlocal()),'%Y-%m-%d %H:%M:%S')


class ResizableImageHolderQLabel(QLabel):
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
        self.video_widget = QVideoWidget()
        self.media_player.setMedia(QMediaContent(QUrl(media_video_url)))
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.pause()
        self.mouseReleaseEvent = self.on_media_state_changed
        self.layout = QVBoxLayout()
        self.layout.addWidget(QLabel("video/gif"))
        self.layout.addWidget(self.video_widget)
        self.setLayout(self.layout)

    def on_media_state_changed(self, event):
        if self.media_player.state() == QMediaPlayer.PausedState or self.media_player.state() == QMediaPlayer.StoppedState:
            self.media_player.play()
        else:
            self.media_player.pause()

# TODO : 3 types of widget : quote, retweet, post
class PinWidget(QWidget):
    def __init__(self, pin, download_img_thread_pool):
        super(PinWidget, self).__init__()
        self.pin = pin
        self.download_img_thread_pool = download_img_thread_pool
        self.init_ui()

    def init_ui(self):
        self.post_layout = QHBoxLayout()
        self.setLayout(self.post_layout)
        rep_author_img_url = None
        tweet, ts = self.pin.content, self.pin.created_at
        author, author_img_url, urls, medias = self.pin.profile_name, self.pin.profile_url, self.pin.urls, self.pin.media_urls
        tweet_text = wrap_text_href(tweet)
        if ts:
            tweet_text += "\n...at " + convert_dt(ts) + "\n"
        dbgp(("Got urls:", urls))
        tweet_text += "\n".join(href_word(url, open_status_link) for url in urls)
        dbgp("final text:{}".format(tweet_text))
        tweet_author_label_img = QLabel()
        self.download_img_thread_pool.register_img_url(author_img_url, tweet_author_label_img.setPixmap)
        self.post_layout.addWidget(tweet_author_label_img)
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
                    media_attachment_label = ResizableImageHolderQLabel()
                    media_attachment_label.setScaledContents(True)
                    self.download_img_thread_pool.register_img_url(media_url, media_attachment_label.setPixmap)
                    tweet_layout.addWidget(media_attachment_label)
        self.post_layout.addLayout(tweet_layout)
        self.post_layout.addStretch(1)
