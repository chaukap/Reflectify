import requests
from requests.sessions import session
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json
import uuid
import time
import urllib
import pandas as pd
import mysql.connector
from flask_sslify import SSLify
import lyricsgenius
from clustering_helpers import get_all_items_in_all_playlists, get_audio_features_for_tracks, get_selected_features, get_all_items_for_playlist
from SqlCacheHandler import SqlCacheHandler
from sklearn.cluster import AgglomerativeClustering
from flask import Flask, make_response, request, redirect, render_template, url_for

app = Flask(__name__)
sslify = SSLify(app)

keys = pd.read_csv("keys.csv")

server = keys.SessionsServer[0]
database = keys.SessionsDb[0]
username = keys.SessionUser[0]
password = keys.SessionPassword[0]

connection = mysql.connector.connect(host=server, database=database, user=username, password=password)
cursor = connection.cursor()

scope = "user-read-recently-played user-read-private user-read-email user-library-read user-library-modify playlist-modify-public"

def authorize(request):
    sessionid = request.cookies.get("ReflectifySession")

    if(sessionid == None):
       return redirect(url_for("login"), code=302)

    cursor.execute(
       "SELECT * FROM sessions WHERE session_id = '{username}'"
       .format(username=sessionid)
    )
    row = cursor.fetchall()
    if(len(row) < 1):
       data = {
          "response_type": "code",
          "redirect_uri": keys.RedirectUri[0],
          "client_id": keys.SpotifyClientId[0],
          "scope": scope
       }
       return redirect("https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(data), code=302)
    elif(len(row) > 1):
       cursor.execute("DELETE FROM sessions WHERE session_id = '{username}'".format(username=sessionid))
       connection.commit()
       data = {
          "response_type": "code",
          "redirect_uri": keys.RedirectUri[0],
          "client_id": keys.SpotifyClientId[0],
          "scope": scope
       }
       return redirect("https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(data), code=302)

    return "success"

@app.route('/cluster/define')
def define_clusters():
   sessionid = request.cookies.get("ReflectifySession")

   sp = spotipy.Spotify(
      auth_manager=SpotifyOAuth(client_id=keys.SpotifyClientId[0],
      client_secret=keys.SpotifyClientSecret[0],
      redirect_uri=keys.RedirectUri[0],
      scope=scope,
      cache_handler=SqlCacheHandler(sessionid))
   )

   user_playlists = pd.DataFrame(sp.current_user_playlists(limit=50, offset=0)['items'])[['id', 'name']]

   return render_template('cluster.html', 
      playlists=user_playlists.to_dict('records'),
      username=sp.me()['display_name'])

@app.route('/cluster/results')
def clustering_results():
   authorization = authorize(request)
   if(authorization != "success"):
      return authorization
   
   n_clusters = request.args.get('clusters', type=int)
   linkage = request.args.get('distance-metric', type=str)
   playlist = request.args.get('playlist', type=str)
   sessionid = request.cookies.get("ReflectifySession")

   sp = spotipy.Spotify(
      auth_manager=SpotifyOAuth(client_id=keys.SpotifyClientId[0],
      client_secret=keys.SpotifyClientSecret[0],
      redirect_uri=keys.RedirectUri[0],
      scope=scope,
      cache_handler=SqlCacheHandler(sessionid))
   )

   items = get_all_items_for_playlist(playlist, sp)
   items = items[items.is_track]
   features = get_audio_features_for_tracks(items.id, sp)
   features = features.merge(items, on='id', how='left')
   clustering_points = get_selected_features(request)

   if(clustering_points == None):
      return redirect(url_for('define_clusters'))

   clustering = AgglomerativeClustering(n_clusters=n_clusters, linkage=linkage)
   clustering.fit(features[clustering_points])
   features['cluster'] = clustering.labels_
   clusters = features.cluster.unique()
   new_playlists = []
   song_id_lists = []
   features = features.groupby('cluster')

   for cluster in clusters:
      new_playlists.append(features.get_group(cluster).to_dict('records'))
      song_id_lists.append(','.join(features.get_group(cluster).id.tolist()))

   return render_template('clustering_results.html', 
      items=new_playlists, 
      song_id_lists=song_id_lists, 
      n_items=len(new_playlists),
      username=sp.me()['display_name'])

@app.route("/playlist/create")
def create_playlist():
   authorization = authorize(request)
   if(authorization != "success"):
      return authorization
      
   sessionid = request.cookies.get("ReflectifySession")
   songs = request.args.get("songs", type=str)
   name = request.args.get("name", type=str)

   sp = spotipy.Spotify(
      auth_manager=SpotifyOAuth(client_id=keys.SpotifyClientId[0],
      client_secret=keys.SpotifyClientSecret[0],
      redirect_uri=keys.RedirectUri[0],
      scope=scope,
      cache_handler=SqlCacheHandler(sessionid))
   )

   new_playlist = sp.user_playlist_create(sp.me()['id'], name, description="Generated by Reflectify")
   sp.user_playlist_add_tracks(sp.me()['id'], new_playlist['id'], songs.split(","))

   return redirect(new_playlist["external_urls"]["spotify"], code=302)

@app.route('/')
def index():
   authorization = authorize(request)
   if(authorization != "success"):
      return authorization

   sessionid = request.cookies.get("ReflectifySession")

   sp = spotipy.Spotify(
      auth_manager=SpotifyOAuth(client_id=keys.SpotifyClientId[0],
      client_secret=keys.SpotifyClientSecret[0],
      redirect_uri=keys.RedirectUri[0],
      scope=scope,
      cache_handler=SqlCacheHandler(sessionid))
   )
   
   return render_template('index.html', 
      username=sp.me()['display_name'])

@app.route('/recentlyplayed')
def recently_played():
   authorization = authorize(request)
   if(authorization != "success"):
      return authorization

   sessionid = request.cookies.get("ReflectifySession")
   count = request.args.get("count")

   if(count == None or int(count) < 1 or int(count) > 50):
      count = 20

   sp = spotipy.Spotify(
      auth_manager=SpotifyOAuth(client_id=keys.SpotifyClientId[0],
      client_secret=keys.SpotifyClientSecret[0],
      redirect_uri=keys.RedirectUri[0],
      scope="user-read-recently-played",
      cache_handler=SqlCacheHandler(sessionid))
   )

   return render_template("recently_played.html", 
      songs=sp.current_user_recently_played(int(count))['items'],
      username=sp.me()['display_name'])

@app.route("/lyrics")
def lyrics():
   song_name = request.args.get("song")
   artist = request.args.get("artist")

   if(song_name == None):
      return "No song specified"

   if(artist == None):
      return "No artist specified"

   genius = lyricsgenius.Genius(keys.GeniusClientAccessToken[0])
   song = genius.search_song(song_name, artist)
   return render_template("lyrics.html", 
      lyrics=song.lyrics.split("\n"),
      username=sp.me()['display_name'])

@app.route('/login')
def login(): 
   sessionid = request.cookies.get("ReflectifySession")

   if(sessionid == None):
      response = make_response(redirect(url_for("index"), code=302))
      session = uuid.uuid4()
      response.set_cookie("ReflectifySession", str(session))
      return response
   
   authorization = authorize(request)
   if(authorization != "success"):
      return authorization

   return redirect(url_for("index"), code=302)

@app.route('/auth')
def auth():
   sessionid = request.cookies.get("ReflectifySession")
   code = request.args.get("code")
   
   if(sessionid == None):
      return make_response("Missing sessionid.")

   response = requests.post("https://accounts.spotify.com/api/token", data={
      "grant_type": "authorization_code",
      "code": str(code),
      "redirect_uri": keys.RedirectUri[0],
      "client_id": keys.SpotifyClientId[0],
      "client_secret": keys.SpotifyClientSecret[0]
   })

   response_body = json.loads(response.text)
   response_body["expires_at"] = int(time.time()) + int(response_body["expires_in"])

   cursor.execute(
      """INSERT INTO sessions
         VALUES ('{session_id}',
                 '{access_token}',
                 '{token_type}',
                 {expires_in},
                 '{refresh_token}',
                 '{scope}',
                 {expires_at})"""
                 .format(**response_body, session_id=sessionid)
   )
   connection.commit()

   return redirect(url_for("index"), code=302)

if __name__ == '__main__':
   app.run(debug=False)