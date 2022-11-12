import json
import requests
import time
import xml.etree.ElementTree as ET

import numpy as np
from tqdm import tqdm


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

        self.WAIT_TIME = 0.2

    def get_library(self):
        """
        Gets Steam library games using Steam url name

        Returns
        -------
        list of dicts
            Records of games in Steam library
        """
        # Get library appids, title, and play time
        r = requests.get(f'https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key={self.web_api_key}&steamid={self.user_id}&include_appinfo=1&include_played_free_games=1')
        time.sleep(self.WAIT_TIME)
        library_list = json.loads(r.text)['response']['games']

        games_records = []
        for item in tqdm(library_list, desc='Steam Library'):
            game = {}
            game['steam_appid'] = item['appid']
            game['title'] = item['name']
            game['playtime'] = item['playtime_forever']
            game['last_played'] = item['rtime_last_played']
            games_records.append(game)
    
        # Get achievements per appid
        for game in tqdm(games_records, desc='Steam Library Achievements'):
            # TODO: Abstracting into own fn
            r = requests.get(f'http://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v0001/?appid={game["steam_appid"]}&key={self.web_api_key}&steamid={self.user_id}')
            time.sleep(self.WAIT_TIME)
            achievements_json = json.loads(r.text)
            
            completed, total, progress = None, None, None
            if achievements_json['playerstats']['success'] and 'achievements' in achievements_json['playerstats']:
                achievements_list = achievements_json['playerstats']['achievements']
                total = 0
                completed = 0
                for a in achievements_list:
                    total += 1
                    completed += a['achieved']  # 1 or 0 based on whether completed
                progress = np.round(completed/total*100, 1)                

            game['achievement_progress'] = progress
            game['completed_achievements'] = completed
            game['total_achievements'] = total

        # TODO Add Store data

        return games_records

    def get_wishlist(self):
        """
        Gets Steam wishlist games using Steam user id

        Returns
        -------
        list of dicts
            Records of games in Steam wishlist
        """
        # Iterate through wishlist pages
        games_records = []
        page_counter = 0
        while page_counter >= 0:
            r = requests.get(f'https://store.steampowered.com/wishlist/profiles/{self.user_id}/wishlistdata/?p={page_counter}', timeout=60)
            time.sleep(0.1)
        
            wishlist = json.loads(r.text)
            if wishlist:
                steam_ids = list(wishlist.keys())
                games_records += [{'steam_appid': int(steam_id), 'title': wishlist[steam_id]['name']} for steam_id in steam_ids]
                page_counter += 1
            else:
                page_counter = -1

        # TODO Add Store data

        return games_records