from bs4 import BeautifulSoup as bs4


class ThumbNailer(object):
    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.main_logger.bot_logger.getChild("ThumbNailer")

    async def get_html(self, url):
        async with self.bot.session.get(url, timeout=30) as response:
            assert response.status == 200
            return await response.read()

    @staticmethod
    async def _soundcloud(self, url):
        html = await ThumbNailer.get_html(self, url)
        try:
            soup = bs4(html, 'html.parser')
            img = soup.find("meta", property="twitter:image")
            return img["content"]
        except Exception as e:
            self.logger.exception("%s" % e)

    async def _bandcamp(self, url):
        html = await ThumbNailer.get_html(self, url)
        try:
            soup = bs4(html, 'html.parser')
            img = soup.find(class_="popupImage").get("href")
            return img
        except Exception as e:
            self.logger.exception("%s" % e)

    async def _vimeo(self, url):
        html = await ThumbNailer.get_html(self, url)
        try:
            soup = bs4(html, 'html.parser')
            img = soup.find("meta", property="og:image")
            return img["content"]
        except Exception as e:
            self.logger.exception("%s" % e)

    @staticmethod
    async def identify(self, identifier, uri):
        if "youtube" in uri:
            thumbnail_url = f"https://img.youtube.com/vi/{identifier}/0.jpg"
            return thumbnail_url
        elif "soundcloud" in uri:
            thumbnail_url = await ThumbNailer._soundcloud(self, url=uri)
            return thumbnail_url
        elif "bandcamp" in uri:
            thumbnail_url = await ThumbNailer._bandcamp(self, url=uri)
            return thumbnail_url
        elif "vimeo" in uri:
            thumbnail_url = await ThumbNailer._vimeo(self, url=uri)
            return thumbnail_url
        else:
            return None
