import aiohttp
import asyncio
from bs4 import BeautifulSoup as BS


class ThumbNailer(object):

	def __init__(self):
		self.url = self

	async def connection(self, url):
		async with aiohttp.ClientSession() as session:
			async with session.get(url, timeout=30) as response:
				assert response.status == 200
				html = await response.read()
				return ThumbNailer.__parse_result(html)

	def __parse_result(html):
		try:
			soup = BS(html, 'html.parser')
			img = soup.find("meta", property="twitter:image")["content"]
			return img
		except Exception as e:
			raise e

	async def identify(self, identifier, uri):
		thumbnail_url = ""
		if "youtube" in uri:
			thumbnail_url = f"https://img.youtube.com/vi/{identifier}/0.jpg"
			return thumbnail_url
		elif "soundcloud" in uri:
			thumbnail_url = await ThumbNailer.connection(ThumbNailer, url=uri)
			return thumbnail_url
		else:
			return None



def thumbnailer(self, identifier, uri):
	thumbnail_url = ""
	if "youtube" in uri:
		thumbnail_url = f"https://img.youtube.com/vi/{identifier}/0.jpg"
		return thumbnail_url
	elif "soundcloud" in uri:
		thumbnail_url = BS(requests.get(uri).text, "html.parser").find("meta", property="twitter:image")["content"]
		return thumbnail_url
	else:
		return None
