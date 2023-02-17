#! /usr/bin/env python3

import pandas as pd
from sqlalchemy import create_engine, text
from ratelimiter import RateLimiter
from tqdm import tqdm

from igdb_api import IGDBClient
from ps_api import PlaystationClient
from steam_api import SteamClient

from config import config  # TODO: Find a better way to manage secrets

database_url = config['database_url']
steam_url_name = config['steam_url_name']
steam_user_id = config['steam_user_id']
steam_web_api_key = config['steam_web_api_key']
igdb_client_id = config['igdb_client_id']
igdb_client_secret = config['igdb_client_secret']
ps_npsso = config['ps_npsso']

# Database engine
engine = create_engine(database_url, echo=True)


def get_game_data():
    with engine.connect() as conn:
        df = pd.read_sql_query(text("""SELECT * FROM games_data;"""), conn)

    return df


def update_db():
    """
    Creates/Recreates vgdb from scratch
    """
    with engine.connect() as conn:
        # Init clients
        steam_client = SteamClient(
            steam_url_name,
            steam_user_id,
            steam_web_api_key
        )
        igdb_client = IGDBClient(
            igdb_client_id,
            igdb_client_secret
        )
        igdb_ratelimiter = RateLimiter(max_calls=3, period=1)
        ps_client = PlaystationClient(
            ps_npsso
        )

        # =====================================================================
        # Get Steam
        # =====================================================================
        steam_library_records = steam_client.get_library()
        steam_wishlist_records = steam_client.get_wishlist()

        # Convert tags to string to store in tables
        for record in steam_library_records:
            record['tags'] = str(record['tags'])
        for record in steam_wishlist_records:
            record['tags'] = str(record['tags']) 

        # Create steam_library table
        conn.execute(text("""DROP TABLE IF EXISTS steam_library;"""))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS steam_library (
                    steam_appid INT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    owned BOOL,
                    playtime FLOAT,
                    last_played INT,
                    achievement_progress FLOAT,
                    completed_achievements INT,
                    total_achievements INT,
                    recent_reviews_percent FLOAT,
                    recent_reviews_count INT,
                    all_reviews_percent FLOAT,
                    all_reviews_count INT,
                    short_description TEXT,
                    tags TEXT
                );
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO steam_library (
                    steam_appid,
                    title,
                    owned,
                    playtime,
                    last_played,
                    achievement_progress,
                    completed_achievements,
                    total_achievements,
                    recent_reviews_percent,
                    recent_reviews_count,
                    all_reviews_percent,
                    all_reviews_count,
                    short_description,
                    tags
                ) VALUES (
                    :steam_appid,
                    :title,
                    :owned,
                    :playtime,
                    :last_played,
                    :achievement_progress,
                    :completed_achievements,
                    :total_achievements,
                    :recent_reviews_percent,
                    :recent_reviews_count,
                    :all_reviews_percent,
                    :all_reviews_count,
                    :short_description,
                    :tags
                );
                """
            ),
            steam_library_records
        )

        # Create steam_wishlist table
        conn.execute(text("""DROP TABLE IF EXISTS steam_wishlist;"""))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS steam_wishlist (
                    steam_appid INT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    owned BOOL,
                    playtime FLOAT,
                    last_played INT,
                    achievement_progress FLOAT,
                    completed_achievements INT,
                    total_achievements INT,
                    recent_reviews_percent FLOAT,
                    recent_reviews_count INT,
                    all_reviews_percent FLOAT,
                    all_reviews_count INT,
                    short_description TEXT,
                    tags TEXT
                );
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO steam_wishlist (
                    steam_appid,
                    title,
                    owned,
                    playtime,
                    last_played,
                    achievement_progress,
                    completed_achievements,
                    total_achievements,
                    recent_reviews_percent,
                    recent_reviews_count,
                    all_reviews_percent,
                    all_reviews_count,
                    short_description,
                    tags
                ) VALUES (
                    :steam_appid,
                    :title,
                    :owned,
                    :playtime,
                    :last_played,
                    :achievement_progress,
                    :completed_achievements,
                    :total_achievements,
                    :recent_reviews_percent,
                    :recent_reviews_count,
                    :all_reviews_percent,
                    :all_reviews_count,
                    :short_description,
                    :tags
                );
                """
            ),
            steam_wishlist_records
        )

        # =====================================================================
        # Get PS
        # =====================================================================
        ps_played_records = ps_client.get_played_titles()
        
        # Convert tags to string to store in tables
        for record in ps_played_records:
            record['genres'] = str(record['genres'])

        # Create ps_played_titles table
        conn.execute(text("""DROP TABLE IF EXISTS ps_played_titles;"""))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS ps_played_titles (
                    ps_np_title_id TEXT NOT NULL,
                    ps_np_comm_id TEXT,
                    title TEXT,
                    console TEXT,
                    playtime FLOAT,
                    trophy_weighted_progress FLOAT,
                    completed_trophies INT,
                    total_trophies INT,
                    first_played TEXT,
                    last_played TEXT,
                    genres TEXT
                );
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO ps_played_titles (
                    ps_np_title_id,
                    ps_np_comm_id,
                    title,
                    console,
                    playtime,
                    trophy_weighted_progress,
                    completed_trophies,
                    total_trophies,
                    first_played,
                    last_played,
                    genres
                ) VALUES (
                    :ps_np_title_id,
                    :ps_np_comm_id,
                    :title,
                    :console,
                    :playtime,
                    :trophy_weighted_progress,
                    :completed_trophies,
                    :total_trophies,
                    :first_played,
                    :last_played,
                    :genres
                );
                """
            ),
            ps_played_records
        )

        # =====================================================================
        # Create ID mapping
        # =====================================================================
        # steam_appid
        df_steam_appid_mapping  = pd.read_sql_query(
            text(
                """
                SELECT steam_appid, title from steam_library
                UNION ALL
                SELECT steam_appid, title from steam_wishlist;
                """
            ),
            conn
        )
        df_steam_appid_mapping['igdb_id'] = None

        for idx, row in tqdm(df_steam_appid_mapping.iterrows(), total=df_steam_appid_mapping.shape[0], desc='Map steam_appid to igdb_id'):
            with igdb_ratelimiter:
                igdb_id = igdb_client.get_igdb_id_by_steam_appid(int(row['steam_appid']))
            if igdb_id:
                df_steam_appid_mapping.at[idx, 'igdb_id'] = igdb_id
            else:
                print(f'No IGDB ID found for ({row["steam_appid"]}) {row["title"]}')

        df_steam_appid_mapping = df_steam_appid_mapping[['igdb_id', 'steam_appid']]

        #ps_np_title_id
        df_ps_np_title_id_mapping  = pd.read_sql_query(
            text(
                """
                SELECT ps_np_title_id, title from ps_played_titles;
                """
            ),
            conn
        )
        df_ps_np_title_id_mapping['igdb_id'] = None

        for idx, row in tqdm(df_ps_np_title_id_mapping.iterrows(), total=df_ps_np_title_id_mapping.shape[0], desc='Map ps_np_title_id to igdb_id'):
            with igdb_ratelimiter:
                igdb_id = igdb_client.get_igdb_id_by_title(row['title'])
            if igdb_id:
                df_ps_np_title_id_mapping.at[idx, 'igdb_id'] = igdb_id
            else:
                print(f'No IGDB ID found for ({row["ps_np_title_id"]}) {row["title"]}')
        
        df_ps_np_title_id_mapping = df_ps_np_title_id_mapping[['igdb_id', 'ps_np_title_id']]

        # Join
        df_steam_appid_mapping = df_steam_appid_mapping.set_index('igdb_id')
        df_ps_np_title_id_mapping = df_ps_np_title_id_mapping.set_index('igdb_id')
        df_id_mapping = df_steam_appid_mapping.join(df_ps_np_title_id_mapping, how='outer')
        id_mapping_records = df_id_mapping.reset_index(names='igdb_id').to_dict('records')

        # Create id_mapping table
        conn.execute(text("""DROP TABLE IF EXISTS id_mapping;"""))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS id_mapping (
                    igdb_id INT,
                    steam_appid INT,
                    ps_np_title_id TEXT
                );
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO id_mapping (
                    igdb_id,
                    steam_appid,
                    ps_np_title_id
                ) VALUES (
                    :igdb_id,
                    :steam_appid,
                    :ps_np_title_id
                );
                """
            ),
            id_mapping_records
        )

        # =====================================================================
        # Get IGDB
        # =====================================================================
        igdb_ids  = pd.read_sql_query(
            text(
                """
                SELECT igdb_id from id_mapping;
                """
            ),
            conn
        ).dropna().drop_duplicates().astype(int)['igdb_id'].values

        igdb_records = []
        for igdb_id in tqdm(igdb_ids, desc='IGDB Game Data'):
            with igdb_ratelimiter:
                record = igdb_client.get_game(igdb_id)
            igdb_records.append(record)

         # Convert tags to string to store in tables
        for record in igdb_records:
            record['platforms'] = str(record['platforms'])
            record['genres'] = str(record['genres'])
            record['themes'] = str(record['themes'])
            record['keywords'] = str(record['keywords'])

        conn.execute(text("""DROP TABLE IF EXISTS igdb_data;"""))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS igdb_data (
                    igdb_id INT UNIQUE,
                    name TEXT,
                    first_release_date INT,
                    platforms TEXT,
                    rating FLOAT,
                    rating_count INT,
                    critics_rating FLOAT,
                    critics_rating_count INT,
                    summary TEXT,
                    storyline TEXT,
                    genres TEXT,
                    themes TEXT,
                    keywords TEXT
                );
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO igdb_data (
                    igdb_id,
                    name,
                    first_release_date,
                    platforms,
                    rating,
                    rating_count,
                    critics_rating,
                    critics_rating_count,
                    summary,
                    storyline,
                    genres,
                    themes,
                    keywords
                ) VALUES (
                    :igdb_id,
                    :name,
                    :first_release_date,
                    :platforms,
                    :rating,
                    :rating_count,
                    :critics_rating,
                    :critics_rating_count,
                    :summary,
                    :storyline,
                    :genres,
                    :themes,
                    :keywords
                );
                """
            ),
            igdb_records
        )
                

if __name__ == '__main__':
    update_db()