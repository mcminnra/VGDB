import json
import pathlib
import time

from fuzzywuzzy import fuzz
from igdb.wrapper import IGDBWrapper
import requests

class IGDBClient():
    """Client class to provide specific api functions to IGDB Wrapper"""

    def __init__(self, client_id: str, client_secret: str):
        # Init wrapper
        access_token = self._get_access_token(client_id, client_secret)
        self._igdb_wrapper = IGDBWrapper(client_id, access_token)

    def _get_access_token(self, client_id: str, client_secret: str) -> str:
        token_path = pathlib.Path.home() / ".vgdb/"
        token_path.mkdir(parents=True, exist_ok=True)
        token_filepath = token_path / "igdb_token.json"
        current_unix_time = int(time.time())

        # If token file exists, check to see if still active and return
        if token_filepath.exists():
            with open(token_filepath, 'r') as f:
                access_json = json.load(f)
            if access_json['expires'] > current_unix_time:
                return access_json['access_token'] 

        # Get IGDB access token
        r = requests.post(f"https://id.twitch.tv/oauth2/token?client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials")
        access_json = json.loads(r.text)        
        access_json['expires'] = current_unix_time + access_json['expires_in'] - 1

        # Write access token
        with open(token_filepath, 'w') as f:
            json.dump(access_json, f)

        return access_json['access_token']

    def get_game(self, igdb_id: int) -> dict:
        """
        Get game metadata from IGDB ID
        """
        byte_array = self._igdb_wrapper.api_request(
            'games',
            #f'fields *; where id = {igdb_id};'
            f'fields id, aggregated_rating, aggregated_rating_count, first_release_date, genres.name, keywords.name, name, platforms.name, rating, rating_count, storyline, summary, themes.name; where id = {igdb_id};'
        )
        games_response = json.loads(byte_array)
        igdb_metadata = games_response[0]

        # Add nulls to response if missing
        fields = [
            'id',
            'aggregated_rating',
            'aggregated_rating_count',
            'first_release_date',
            'genres',
            'keywords',
            'name',
            'platforms',
            'rating',
            'rating_count',
            'storyline',
            'summary',
            'themes'
        ]
        for k in fields:
            if k not in igdb_metadata:
                igdb_metadata[k] = None

        # Convert expanded fields into lists
        igdb_metadata['genres'] = [item['name'] for item in igdb_metadata['genres']] if igdb_metadata['genres'] else None
        igdb_metadata['keywords'] = [item['name'] for item in igdb_metadata['keywords']] if igdb_metadata['keywords'] else None
        igdb_metadata['platforms'] = [item['name'] for item in igdb_metadata['platforms']] if igdb_metadata['platforms'] else None
        igdb_metadata['themes'] = [item['name'] for item in igdb_metadata['themes']] if igdb_metadata['themes'] else None

        # Rename confusing fields
        igdb_metadata['igdb_id'] = igdb_metadata.pop('id')
        igdb_metadata['critics_rating'] = igdb_metadata.pop('aggregated_rating')
        igdb_metadata['critics_rating_count'] = igdb_metadata.pop('aggregated_rating_count')

        # Reorder
        order = [
            'igdb_id',
            'name',
            'first_release_date',
            'platforms',
            'rating',
            'rating_count',
            'critics_rating',
            'critics_rating_count',
            'summary', 
            'storyline',
            'genres',
            'themes',
            'keywords'
        ]
        igdb_metadata = {k: igdb_metadata[k] for k in order}

        return igdb_metadata

    def get_igdb_id_by_steam_appid(self, steam_appid: int) -> int:
        """
        Get IGDB ID using Steam ID
        """
        igdb_id = None

        # Search game's linked websites searching for ones with steam_appid
        search_string = f'/{steam_appid}'
        byte_array = self._igdb_wrapper.api_request(
            'websites',
            f'fields *; where url = *"{search_string}"* & category = 13;'
        )
        websites_response = json.loads(byte_array)

        # More than 1 game has the same steam id website. Take the one with the most reviews or first released
        if len(websites_response) > 1:
            search_igdb_ids = str(tuple([r['game'] for r in websites_response]))
            byte_array = self._igdb_wrapper.api_request(
                'games',
                f'fields *; where id = {search_igdb_ids} & category != (5, 6, 7);'  # No mods, episodes, or seasons
            )
            games_response = json.loads(byte_array)

            for game in games_response:
                if 'total_rating_count' not in game:
                    game['total_rating_count'] = 0
                if 'first_release_date' not in game:
                    game['first_release_date'] = int(time.time())
                game['first_release_date'] *= -1

            igdb_id = int(sorted(games_response, key=lambda x: (x['total_rating_count'], x['first_release_date']), reverse=True)[0]['id'])

        elif len(websites_response) == 1:
            igdb_id = int(websites_response[0]['game'])

        return igdb_id

    def get_igdb_id_by_title(self, title: str) -> int:
        """
        Get IGDB ID using title
        """
        # fields id, aggregated_rating, aggregated_rating_count, category.*, first_release_date, genres.*, keywords.*, name, rating, rating_count, storyline, summary, tags.*, themes.*, total_rating, total_rating_count;
        search_string = title.replace('®', '').replace('™', '')
        byte_array = self._igdb_wrapper.api_request(
            'games',
            f'fields id, name; search "{search_string}"; limit 500;'
        )
        games_response = json.loads(byte_array)

        igdb_id = None
        if len(games_response) > 1:
            # Fuzzy match best result from search to input title
            games_fuzzy = []
            for game in games_response:
                games_fuzzy.append((game['id'], game['name'], fuzz.ratio(title, game['name'])))
            games_fuzzy = sorted(games_fuzzy, key=lambda x: x[2], reverse=True)
            igdb_id = games_fuzzy[0][0]
        elif len(games_response) == 1:
            igdb_id = games_response[0]['id']

        return igdb_id
