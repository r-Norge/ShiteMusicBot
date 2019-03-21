import aiohttp
from bs4 import BeautifulSoup as bs4

session = aiohttp.ClientSession()


class ThumbNailer(object):

    async def get_img(self, url):
            async with session.get(url, timeout=30) as response:
                assert response.status == 200
                html = await response.read()
                return html

    async def __parse_result(html):
        try:
            soup = bs4(html, 'html.parser')
            img = soup.find("meta", property="twitter:image")["content"]
            return img
        except Exception as e:
            raise e

    async def identify(self, identifier, uri):
        if "youtube" in uri:
            thumbnail_url = f"https://img.youtube.com/vi/{identifier}/0.jpg"
            return thumbnail_url
        elif "soundcloud" in uri:
            thumbnail_url = await ThumbNailer.__parse_result(await ThumbNailer.get_img(ThumbNailer, uri))
            return thumbnail_url
        else:
            return None


class Youtube:

    async def realated_videos(self, num):
        url = f"https://www.googleapis.com/youtube/v3/search" \
            f"?part=snippet" \
            f"&relatedToVideoId={num}" \
            f"&type=video" \
            f"&maxResults=3" \
            f"&key={self.youtube['dev_key']}"
        ids = []

        async with session.get(url, timeout=30) as response:
            assert response.status == 200
            html = await response.json()
            if html["pageInfo"]["totalResults"] == 0:
                print(f"search_result None")
                return None
            for search_result in html["items"]:
                if search_result['id']['kind'] == 'youtube#video':
                    ids.append(search_result['id']['videoId'])
        return ids
