from time import perf_counter

from bs4 import BeautifulSoup as bs4

from bot import Bot


class Thumbnailer(object):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = self.bot.main_logger.bot_logger.getChild("Thumbnailer")

    async def get_html(self, url: str):
        async with self.bot.session.get(url, timeout=3) as response:
            assert response.status == 200
            return await response.read()

    async def _soundcloud(self, url: str) -> str:
        perf_start = perf_counter()
        html = await self.get_html(url)
        try:
            soup = bs4(html, 'html.parser')
            soup = soup.find("meta", property="twitter:image")
            img = soup.get("content", default="")
            perf_stop = perf_counter()
            self.logger.debug("Took %s to find thumbnail from Soundcloud" % (perf_stop - perf_start))
            return img
        except Exception as e:
            self.logger.exception("%s" % e)
            return ""

    async def _bandcamp(self, url: str) -> str:
        perf_start = perf_counter()
        html = await self.get_html(url)
        try:
            soup = bs4(html, 'html.parser')
            soup = soup.find(class_="popupImage")
            img = soup.get("href", default="")
            perf_stop = perf_counter()
            self.logger.debug("Took %s to find thumbnail from Bandcamp" % (perf_stop - perf_start))
            return img
        except Exception as e:
            self.logger.exception("%s" % e)
            return ""

    async def _vimeo(self, url: str) -> str:
        perf_start = perf_counter()
        html = await self.get_html(url)
        try:
            soup = bs4(html, 'html.parser')
            soup = soup.find("meta", property="og:image")
            img = soup.get("content", default="")
            perf_stop = perf_counter()
            self.logger.debug("Took %s to find thumbnail from Vimeo" % (perf_stop - perf_start))
            return img
        except Exception as e:
            self.logger.exception("%s" % e)
            return ""

    async def identify(self, identifier: str, uri: str) -> str:
        if "youtube" in uri:
            thumbnail_url = f"https://img.youtube.com/vi/{identifier}/0.jpg"
            return thumbnail_url
        elif "soundcloud" in uri:
            thumbnail_url = await self._soundcloud(url=uri)
            return thumbnail_url
        elif "bandcamp" in uri:
            thumbnail_url = await self._bandcamp(url=uri)
            return thumbnail_url
        elif "vimeo" in uri:
            thumbnail_url = await self._vimeo(url=uri)
            return thumbnail_url
        else:
            return ""
