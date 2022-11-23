from concurrent.futures import as_completed
import json
import time
import xml.etree.ElementTree as ET

from lxml import html
import numpy as np
import requests
from requests_futures.sessions import FuturesSession


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

        self.session = FuturesSession()

        self.WAIT_TIME = 0.3

    def get_library(self):
        """
        Gets Steam library games using Steam url name

        Returns
        -------
        list of dicts
            Records of games in Steam library
        """
        # Get library appids, title, and play time
        start = time.time()
        print('Steam Library...')
        r = requests.get(f'https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key={self.web_api_key}&steamid={self.user_id}&include_appinfo=1&include_played_free_games=1')
        time.sleep(self.WAIT_TIME)
        library_list = json.loads(r.text)['response']['games']

        games_records = []
        for item in library_list:
            game = {}
            game['steam_appid'] = item['appid']
            game['title'] = item['name']
            game['owned'] = 'Yes'
            game['playtime'] = item['playtime_forever']
            game['last_played'] = item['rtime_last_played']
            games_records.append(game)
        print(f'Steam Library [{time.time()-start:.2f} seconds]')
    
        # Achievements
        start = time.time()
        print('Steam Library Achievements...')
        games_records = self._enrich_with_achievements(games_records)
        print(f'Steam Library Achievements [{time.time()-start:.2f} seconds]')

        # Store data
        start = time.time()
        print('Steam Library Store Page Data...')
        games_records = self._enrich_with_store_data(games_records)
        print(f'Steam Library Store Page Data [{time.time()-start:.2f} seconds]')

        return games_records

    def get_wishlist(self):
        """
        Gets Steam wishlist games using Steam user id

        Returns
        -------
        list of dicts
            Records of games in Steam wishlist
        """
        games_records = []

        # Iterate through wishlist pages
        start = time.time()
        print('Steam Wishlist...')
        page_counter = 0
        while page_counter >= 0:
            r = requests.get(f'https://store.steampowered.com/wishlist/profiles/{self.user_id}/wishlistdata/?p={page_counter}', timeout=60)
            time.sleep(self.WAIT_TIME)
            wishlist = json.loads(r.text)

            if wishlist:
                steam_ids = list(wishlist.keys())
                games_records += [{'steam_appid': int(steam_id), 'title': wishlist[steam_id]['name']} for steam_id in steam_ids]
                page_counter += 1
            else:
                page_counter = -1

        # Add "None"s to fit steam_library's schema
        for game in games_records:
            game['owned'] = 'No'
            game['playtime'] = None
            game['last_played'] = None
            game['achievement_progress'] = None
            game['completed_achievements'] = None
            game['total_achievements'] = None
        print(f'Steam Wishlist [{time.time()-start:.2f} seconds]')

        # Store data
        start = time.time()
        print('Steam Wishlist Store Page Data...')
        games_records = self._enrich_with_store_data(games_records)
        print(f'Steam Wishlist Store Page Data [{time.time()-start:.2f} seconds]')

        return games_records

    def _enrich_with_achievements(self, games):
        """
        Async enriches records list with achievements data
        """
        futures=[]
        for game in games:
            future = self.session.get(f'http://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v0001/?appid={game["steam_appid"]}&key={self.web_api_key}&steamid={self.user_id}')
            future.game = game
            futures.append(future)

        games_with_achieves = []
        for future in as_completed(futures):
            try:
                # Get response
                resp = future.result()
                game = future.game
                achievements_json = resp.json()

                # Handle status
                if resp.status_code == 400:
                    print(f'No achievements for [{game["steam_appid"]}] {game["title"]}')
                    continue
                elif resp.status_code > 299:
                    raise Exception

                # Process achievements
                completed, total, progress = None, None, None
                if achievements_json['playerstats']['success'] and 'achievements' in achievements_json['playerstats']:
                    achievements_list = achievements_json['playerstats']['achievements']
                    total = 0
                    completed = 0
                    for a in achievements_list:
                        total += 1
                        completed += a['achieved']  # 1 or 0 based on whether completed
                    progress = np.round(completed/total*100, 1)                
                else:
                    print(f'No achievements for [{game["steam_appid"]}] {game["title"]}')

                game['achievement_progress'] = progress
                game['completed_achievements'] = completed
                game['total_achievements'] = total
                games_with_achieves.append(game)
            except:
                print(f'[{resp.status_code}] on {future.game["title"]}')
                import sys; sys.exit(1)

        return games_with_achieves

    def _enrich_with_store_data(self, games):
        """
        Async enriches records list with store data
        """
        futures=[]
        for game in games:
            future = self.session.get(f'https://store.steampowered.com/app/{game["steam_appid"]}')
            future.game = game
            futures.append(future)

        games_with_store_data = []
        for future in as_completed(futures):
            try:
                # Get response
                resp = future.result()
                game = future.game
                steam_store_tree = html.fromstring(resp.text)

                # Handle status
                if resp.status_code > 299:
                    raise Exception

                # TODO: Check to see if HTML is malformed

                #== Reviews
                reviews = [review.strip() for review in steam_store_tree.xpath('//span[@class="nonresponsive_hidden responsive_reviewdesc"]/text()') if '%' in review]
                reviews = [r.replace(',', '').replace('%', '') for r in reviews]
                
                # Grab only numbers from reviews
                if len(reviews) == 1:
                    #if no recent reviews, make recent the same as all
                    recent_r = [int(s) for s in reviews[0].split() if s.isdigit()]
                    all_r = [int(s) for s in reviews[0].split() if s.isdigit()]
                elif len(reviews) == 0:
                    #if no reviews, set to 0
                    recent_r = [0, 0]
                    all_r = [0, 0]
                else: 
                    recent_r = [int(s) for s in reviews[0].split() if s.isdigit()][:2]
                    all_r = [int(s) for s in reviews[1].split() if s.isdigit()]

                game['recent_reviews_percent'] = recent_r[0]
                game['recent_reviews_count'] = recent_r[1]
                game['all_reviews_percent'] = all_r[0]
                game['all_reviews_count'] = all_r[1]

                #== Short Description
                desc_element = steam_store_tree.xpath('//div[@class="game_description_snippet"]/text()')
                game['short_description'] = str(desc_element[0]).strip().replace("\r", "").replace("\n", "") if desc_element else ""

                #== Tags
                tags_raw = steam_store_tree.xpath('//a[@class="app_tag"]/text()')
                game['tags'] = [tag.strip() for tag in tags_raw] if tags_raw else list()

                games_with_store_data.append(game)
            
            except:
                print(f'[{resp.status_code}] on {future.game["title"]}')
                import sys; sys.exit(1)

        return games_with_store_data 

    def get_achievements_data(self, appid):
        """
        Returns achievement data for a given appid

        Returns
        -------
        dict
            Various achievement metadata for appid
        """
        achieve_data = {}

        r = requests.get(f'http://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v0001/?appid={appid}&key={self.web_api_key}&steamid={self.user_id}')
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

        achieve_data['achievement_progress'] = progress
        achieve_data['completed_achievements'] = completed
        achieve_data['total_achievements'] = total

        return achieve_data

    def get_store_page_data(self, appid):
        """
        Returns data from Steam store page for a given appid

        Returns
        -------
        dict
            Various store metadata for appid
        """
        store_data = {}

        r = requests.get(f'https://store.steampowered.com/app/{appid}', timeout=60)
        time.sleep(self.WAIT_TIME)
        steam_store_tree = html.fromstring(r.text)

        #== Reviews
        reviews = [review.strip() for review in steam_store_tree.xpath('//span[@class="nonresponsive_hidden responsive_reviewdesc"]/text()') if '%' in review]
        reviews = [r.replace(',', '').replace('%', '') for r in reviews]
        
        # Grab only numbers from reviews
        if len(reviews) == 1:
            #if no recent reviews, make recent the same as all
            recent_r = [int(s) for s in reviews[0].split() if s.isdigit()]
            all_r = [int(s) for s in reviews[0].split() if s.isdigit()]
        elif len(reviews) == 0:
            #if no reviews, set to 0
            recent_r = [0, 0]
            all_r = [0, 0]
        else: 
            recent_r = [int(s) for s in reviews[0].split() if s.isdigit()][:2]
            all_r = [int(s) for s in reviews[1].split() if s.isdigit()]

        store_data['recent_reviews_percent'] = recent_r[0]
        store_data['recent_reviews_count'] = recent_r[1]
        store_data['all_reviews_percent'] = all_r[0]
        store_data['all_reviews_count'] = all_r[1]

        #== Short Description
        desc_element = steam_store_tree.xpath('//div[@class="game_description_snippet"]/text()')
        store_data['short_description'] = str(desc_element[0]).strip().replace("\r", "").replace("\n", "") if desc_element else ""

        #== Tags
        tags_raw = steam_store_tree.xpath('//a[@class="app_tag"]/text()')
        store_data['tags'] = [tag.strip() for tag in tags_raw] if tags_raw else list()

        return store_data