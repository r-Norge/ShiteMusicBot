import requests
from bs4 import BeautifulSoup as BS

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
