__all__ = ['SqlCacheHandler']

import spotipy
import pandas as pd
import logging
import mysql.connector

logger = logging.getLogger(__name__)

class SqlCacheHandler(spotipy.cache_handler.CacheHandler):
    """
    Handles reading and writing cached Spotify authorization tokens
    as json files on disk.
    """

    def __init__(self,
                 username):
        """
        Parameters:
             * username: The sessionId of the user.
        """
        self.username = username

        keys = pd.read_csv("keys.csv")

        server = keys.SessionsServer[0]
        database = keys.SessionsDb[0]
        username = keys.SessionUser[0]
        password = keys.SessionPassword[0]
        
        self.connection = mysql.connector.connect(host=server, database=database, user=username, password=password)
        self.cursor = self.connection.cursor()

    def get_cached_token(self):
        self.cursor.execute(
            "SELECT * FROM sessions WHERE session_id = '{username}'"
            .format(username=self.username)
        )
        rows = self.cursor.fetchall()

        if(len(rows) != 1):
            return None

        row = rows[0]
        token = {
            'access_token': row[1],
            'token_type': row[2],
            'expires_in': row[3],
            'refresh_token': row[4],
            'scope': row[5],
            'expires_at': row[6]
        }

        return token

    def save_token_to_cache(self, token_info):
        try:
            self.cursor.execute(
                """INSERT INTO sessions
                   VALUES ('{session_id}',
                           '{access_token}',
                           '{token_type}',
                            {expires_in},
                           '{refresh_token}',
                           '{scope}',
                            {expires_at}
                           )"""
                 .format(**token_info, session_id=self.username)
            )
            self.connection.commit()
        except Exception:
            logger.warning('Couldn\'t write token to DB for user: %s',
                           self.username)