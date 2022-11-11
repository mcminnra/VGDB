import json
import requests
import time
import xml.etree.ElementTree as ET


class SteamClient():
    """
    API Client for Steam

    Attributes
    ----------
    url_name : str
        Steam URL Name (https://steamcommunity.com/id/<your_steam_url_name>/)
    user_id : str
        Steam User ID  (https://store.steampowered.com/account/ => Steam ID: <Some Number>)
    web_api_key : str
        Steam API key
    """

    def __init__(self, url_name, user_id, web_api_key):
        self.url_name = url_name
        self.user_id = user_id
        self.web_api_key = web_api_key

    def get_library(self):
        """
        Gets Steam library games using Steam url name

        Returns
        -------
        list of dicts
            Records of games in Steam library
        """
        r = requests.get(f'https://steamcommunity.com/id/{self.url_name}/games?tab=all&xml=1', timeout=60)
        time.sleep(0.1)
        root = ET.fromstring(r.text)[2]
    
        games = []
        for library_item in root.findall('game'):
            game = {}
            game['steam_appid'] = int(library_item.find('appID').text)
            game['title'] = library_item.find('name').text
            games.append(game)

        return games

    def get_wishlist(self):
        """
        Gets Steam wishlist games using Steam user id

        Returns
        -------
        list of dicts
            Records of games in Steam wishlist
        """
        # Iterate through wishlist pages
        games = []
        page_counter = 0
        while page_counter >= 0:
            r = requests.get(f'https://store.steampowered.com/wishlist/profiles/{self.user_id}/wishlistdata/?p={page_counter}', timeout=60)
            time.sleep(0.1)
        
            wishlist = json.loads(r.text)
            if wishlist:
                steam_ids = list(wishlist.keys())
                games += [{'steam_appid': int(steam_id), 'title': wishlist[steam_id]['name']} for steam_id in steam_ids]
                page_counter += 1
            else:
                page_counter = -1

        return games