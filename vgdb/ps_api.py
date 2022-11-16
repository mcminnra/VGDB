import json
import requests
import time
from urllib.parse import urlparse
from urllib.parse import parse_qs

from selenium import webdriver
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
            print(r.text)

            if len(trophy_title['trophyTitles']) > 0:
                title['ps_np_title_id'] = trophy_title['npTitleId']
                title['ps_np_comm_id'] = trophy_title['trophyTitles'][0]['npCommunicationId']
                title['trophy_progress'] = trophy_title['trophyTitles'][0]['progress']  # Can there be multiple trophy sets per npTitleId?
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

        return titles

    def get_purchased_games(self):
        #  "https://web.np.playstation.com/api/graphql/v1/op?operationName=getPurchasedGameList&variables={{\"isActive\":true,\"platform\":[\"ps3\",\"ps4\",\"ps5\"],\"start\":{0},\"size\":{1},\"subscriptionService\":\"NONE\"}}&extensions={{\"persistedQuery\":{{\"version\":1,\"sha256Hash\":\"2c045408b0a4d0264bb5a3edfed4efd49fb4749cf8d216be9043768adff905e2\"}}}}
        # Get auth code

        # Init headless chrome
        # op = webdriver.ChromeOptions()
        # op.add_argument('headless')
        # driver = webdriver.Chrome(options=op)

        driver = webdriver.Chrome(
            executable_path='/mnt/c/Users/mcmin/projects/VGDB/bin/chromedriver'
        )

        driver.get('https://web.np.playstation.com/api/session/v1/signin?redirect_uri=https://io.playstation.com/central/auth/login%3FpostSignInURL=https://www.playstation.com/home%26cancelURL=https://www.playstation.com/home&smcid=web:pdc')

        # # Get cookies from a PS login
        # # NOTE: You need to be log
        # session = requests.Session()
        # print(session.cookies.get_dict())
        # login_url = 'https://web.np.playstation.com/api/session/v1/signin?redirect_uri=https://io.playstation.com/central/auth/login%3FpostSignInURL=https://www.playstation.com/home%26cancelURL=https://www.playstation.com/home&smcid=web:pdc'
        # r = session.get(
        #     login_url
        # )
        # print(session.cookies.get_dict())

        # r = session.get(
        #     'https://web.np.playstation.com/api/graphql/v1/op?operationName=getPurchasedGameList&variables={{"isActive":true,"platform":["ps3","ps4","ps5"],"start":0,"size":24,"subscriptionService":"NONE"}}&extensions={{"persistedQuery":{{"version":1,"sha256Hash":"2c045408b0a4d0264bb5a3edfed4efd49fb4749cf8d216be9043768adff905e2"}}}}',
        #     cookies=cookies,
        #     allow_redirects=False
        # )
        # print(r.text)

        

