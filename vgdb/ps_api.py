from datetime import datetime
import json
import time
from urllib.parse import urlparse
from urllib.parse import parse_qs

import numpy as np
import requests
from tqdm import tqdm


class PlaystationClient():

    def __init__(self, npsso):
        self.npsso = npsso
        self.access_token = None

        self.WAIT_TIME = 0.5

        if not self.access_token:
            self.access_token = self._get_access_token(self.npsso)

    def _get_access_token(self, npsso):
        """Return auth code from PS NPSSO"""

        # Get auth code
        cookies = {'npsso': npsso}

        r = requests.get(
            'https://ca.account.sony.com/api/authz/v3/oauth/authorize?access_type=offline&client_id=ac8d161a-d966-4728-b0ea-ffec22f69edc&redirect_uri=com.playstation.PlayStationApp%3A%2F%2Fredirect&response_type=code&scope=psn%3Amobile.v1%20psn%3Aclientapp',
            cookies=cookies,
            allow_redirects=False
        )
        time.sleep(self.WAIT_TIME)
        auth_code = parse_qs(urlparse(r.headers['location']).query)['code']

        # Get access token
        data = {
            'code': auth_code,
            'redirect_uri': "com.playstation.PlayStationApp://redirect",
            'grant_type': "authorization_code",
            'token_format': "jwt"
        }
        headers = {
            "Authorization": "Basic YWM4ZDE2MWEtZDk2Ni00NzI4LWIwZWEtZmZlYzIyZjY5ZWRjOkRFaXhFcVhYQ2RYZHdqMHY="
        }
        r = requests.post(
            "https://ca.account.sony.com/api/authz/v3/oauth/token",
            data=data,
            headers=headers
        )
        time.sleep(self.WAIT_TIME)
        access_token = json.loads(r.text)['access_token']

        return access_token

    def get_played_titles(self):
        # Get titles
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        r = requests.get(
            "https://m.np.playstation.com/api/gamelist/v2/users/me/titles?categories=ps4_game,ps5_native_game&limit=250&offset=0",
            headers=headers
        )
        time.sleep(self.WAIT_TIME)
        titles = json.loads(r.text)['titles']
        titles = [
            {
                'ps_np_title_id': title['titleId'],
                'ps_np_comm_id': None,
                'title': title['name'],
                'console': title['category'],
                'playtime': title['playDuration'],
                'trophy_weighted_progress': None,
                'completed_trophies': None,
                'total_trophies': None,
                'first_played': title['firstPlayedDateTime'],
                'last_played': title['lastPlayedDateTime'],
                'genres': title['concept']['genres']
                
            } for title in titles
        ]

        # Convert datetime str to unix epoch
        for title in titles:
            title['first_played'] = datetime.strptime(title['first_played'], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()
            title['last_played'] = datetime.strptime(title['last_played'], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()

        # Get trophy information
        for title in tqdm(titles, desc='Playstation Trophies'):
            headers = {
                "Authorization": f"Bearer {self.access_token}"
                }
            r = requests.get(
                f'https://m.np.playstation.com/api/trophy/v1/users/me/titles/trophyTitles?npTitleIds={title["ps_np_title_id"]}',
                headers=headers
            )
            time.sleep(self.WAIT_TIME)
            # NOTE: In the future, you can supply multiple np_title_ids => npTitleIds={",".join(query_np_title_ids)} of maybe max 5 ids
            trophy_title = json.loads(r.text)['titles'][0]

            if len(trophy_title['trophyTitles']) > 0:
                title['ps_np_comm_id'] = trophy_title['trophyTitles'][0]['npCommunicationId']
                title['trophy_weighted_progress'] = trophy_title['trophyTitles'][0]['progress']  # Can there be multiple trophy sets per npTitleId?
                title['completed_trophies'] = \
                    int(trophy_title['trophyTitles'][0]["earnedTrophies"]['bronze']) +\
                    int(trophy_title['trophyTitles'][0]["earnedTrophies"]['silver']) +\
                    int(trophy_title['trophyTitles'][0]["earnedTrophies"]['gold']) +\
                    int(trophy_title['trophyTitles'][0]["earnedTrophies"]['platinum'])
                title['total_trophies'] = \
                    int(trophy_title['trophyTitles'][0]["definedTrophies"]['bronze']) +\
                    int(trophy_title['trophyTitles'][0]["definedTrophies"]['silver']) +\
                    int(trophy_title['trophyTitles'][0]["definedTrophies"]['gold']) +\
                    int(trophy_title['trophyTitles'][0]["definedTrophies"]['platinum'])

        # Process playtime into a float
        for title in titles:
            playtime_str = title['playtime']
            playtime_str = playtime_str[2:]  # Remove 'PT' at start

            # Example: 'PT14H5M57S'
            playtime_hours = 0
            if 'H' in playtime_str:
                hours, playtime_str = playtime_str.split('H')
                playtime_hours += float(hours)
            if 'M' in playtime_str:
                minutes, playtime_str = playtime_str.split('M')
                playtime_hours += (float(minutes)/60)
            if 'S' in playtime_str:
                seconds, playtime_str = playtime_str.split('S')
                playtime_hours += (float(seconds)/360)

            playtime_minutes = playtime_hours*60

            title['playtime'] = np.round(playtime_minutes, 1)

        return titles
