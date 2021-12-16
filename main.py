import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json
import uuid
import time
import urllib
import io
from PIL import Image
import base64
import pandas as pd
import mysql.connector
from flask_sslify import SSLify
import lyricsgenius
from wordcloud import WordCloud
from clustering_helpers import get_all_items_in_all_playlists, get_audio_features_for_tracks, get_selected_features, get_all_items_for_playlist
from wordcloud_helpers import clean_lyrics, grey_color_func
from SqlCacheHandler import SqlCacheHandler
from sklearn.cluster import AgglomerativeClustering
from flask import Flask, make_response, request, redirect, render_template, url_for
from os.path import exists
import random
import os
import datetime

app = Flask(__name__)
sslify = SSLify(app)

keys = pd.read_csv("keys.csv")

environment = "production"

server = keys.SessionsServer[0]
database = keys.SessionsDb[0]
username = keys.SessionUser[0]
password = keys.SessionPassword[0]

connection = None
cursor = None
if environment == "production":
   connection = mysql.connector.connect(host=server, database=database, user=username, password=password, ssl_key='client-key.pem', ssl_cert='client-cert.pem', ssl_ca='server-ca.pem')
   cursor = connection.cursor()

scope = "user-read-recently-played user-read-private user-read-email user-library-read user-library-modify playlist-modify-public ugc-image-upload"

def authorize(request):
   sessionid = request.cookies.get("ReflectifySession")

   if(sessionid == None):
      return redirect(url_for("login"), code=302)

   if environment == "production":
      cursor.execute(
         "SELECT * FROM sessions WHERE session_id = '{username}'"
         .format(username=sessionid))
    
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
   elif exists("./.cache"):
      return "success"
   else:
      data = {
         "response_type": "code",
         "redirect_uri": keys.RedirectUri[0],
         "client_id": keys.SpotifyClientId[0],
         "scope": scope
      }
      return redirect("https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(data), code=302)

@app.route('/cluster/define')
def define_clusters():
   sessionid = request.cookies.get("ReflectifySession")

   sp = get_spotify_client(sessionid)

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

   sp = get_spotify_client(sessionid)

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

   sp = get_spotify_client(sessionid)

   new_playlist = sp.user_playlist_create(sp.me()['id'], name, description="Generated by Reflectify")
   sp.user_playlist_add_tracks(sp.me()['id'], new_playlist['id'], songs.split(","))

   return redirect(new_playlist["external_urls"]["spotify"], code=302)

@app.route('/')
def index():
   authorization = authorize(request)
   if(authorization != "success"):
      return render_template('index.html', username=None)

   sessionid = request.cookies.get("ReflectifySession")

   try:
      sp = get_spotify_client(sessionid)
      username = sp.me()['display_name']
   except Exception as e:
      print(e)
      return redirect(url_for("signup"), code=302)
   
   return render_template('index.html', 
      username=username)

@app.route("/wordcloud/make")
def make_wordcloud():
   authorization = authorize(request)
   if(authorization != "success"):
      return authorization
   sessionid = request.cookies.get("ReflectifySession")

   sp = get_spotify_client(sessionid)

   user_playlists = pd.DataFrame(sp.current_user_playlists(limit=50, offset=0)['items'])[['id', 'name']]

   return render_template('wordcloud_make.html', 
      playlists=user_playlists.to_dict('records'),
      username=sp.me()['display_name'])

@app.route("/wordcloud/upload", methods = ['POST'])
def upload_wordcloud():
   authorization = authorize(request)
   if(authorization != "success"):
      return authorization

   request_data = request.values

   playlist_id = request_data["playlist_id"]
   if(playlist_id == None):
      return "No playlist id."

   image = request_data["image"]
   if(image == None):
      return "No image."

   sessionid = request.cookies.get("ReflectifySession")
   sp = get_spotify_client(sessionid)

   sp.playlist_upload_cover_image(playlist_id, image)
   playlist = sp.playlist(playlist_id)

   return redirect(playlist["external_urls"]["spotify"], code=302)

@app.route("/wordcloud/show")
def show_wordcloud():
   authorization = authorize(request)
   if(authorization != "success"):
      return authorization

   playlist_id = request.args.get("playlist")
   
   if(playlist_id == None):
      return "No playlist id."
   sessionid = request.cookies.get("ReflectifySession")

   sp = get_spotify_client(sessionid)

   genius = lyricsgenius.Genius(keys.GeniusClientAccessToken[0])
   genius.verbose = False
   genius.remove_section_headers = True
   genius.skip_non_songs = False
   
   items = get_all_items_for_playlist(playlist_id, sp)

   # The genius api is too slow to use a large playlist
   if items.shape[0] > 8:
      items = items.iloc[[random.randint(0, items.shape[0] - 1) for _ in range(0, 7)]]

   songs = items.apply(lambda y: genius.search_song(y.song, y.artist), axis=1)
   lyrics = songs.map(lambda t: "" if t == None else t.lyrics)

   cleaned_lyrics = lyrics.map(lambda t: clean_lyrics(t))
   text = " ".join(cleaned_lyrics.tolist())
   wordcloud = WordCloud(height=520, width=520).generate(text)
   wordcloud.recolor(color_func=grey_color_func, random_state=3)
   image = Image.frombytes('RGB', (520, 520), bytes(wordcloud.to_array()))

   with io.BytesIO() as output:
      image.save(output, format="PNG")
      contents = output.getvalue()

   playlist = sp.playlist(playlist_id)

   return render_template("wordcloud_show.html", 
      image=base64.b64encode(contents).decode(),
      username=sp.me()['display_name'],
      playlist_name=playlist['name'],
      playlist_id=playlist_id)

@app.route("/signup")
def signup():
   return render_template("request_access.html")

@app.route("/request", methods = ['POST'])
def request_access():
   email = request.values["email"]
   sessionid = request.cookies.get("ReflectifySession")

   response = make_response(render_template("request_success.html",email=email))
   response.set_cookie('ReflectifySession', '', expires=0)

   if environment == "production" and sessionid is not None:
      cursor.execute(
         """DELETE FROM sessions
            WHERE session_id = '{session_id}'"""
                  .format(session_id=sessionid)
      )
      connection.commit()
   else:
      os.remove(".cache")

   if environment == "production":
      cursor.execute(
         """INSERT INTO access_requests
            VALUES ('{email}', '{time}')"""
                  .format(email=email, time=str(datetime.datetime.utcnow()))
      )
      connection.commit()
   
   return response

@app.route('/lanadelrey')
def lana():
   return render_template("Lana_network.html")

@app.route('/login')
def login():
   sessionid = request.cookies.get("ReflectifySession")
   response = make_response(redirect(url_for("login"), code=302))

   if sessionid == None:
      response.set_cookie("ReflectifySession", str(uuid.uuid4()))
      return response
   
   authorization = authorize(request)
   if(authorization != "success"):
      return authorization

   return redirect(url_for("index"), code=302)

@app.route("/logout")
def logout():
   sessionid = request.cookies.get("ReflectifySession")

   response = make_response(redirect(url_for("index"), code=302))
   response.set_cookie('ReflectifySession', '', expires=0)

   if environment == "production" and sessionid is not None:
      cursor.execute(
         """DELETE FROM sessions
            WHERE session_id = '{session_id}'"""
                  .format(session_id=sessionid)
      )
      connection.commit()
   else:
      os.remove(".cache")

   return response

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

   if environment == "production":
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
   else:
      f = open(".cache", "w")
      json.dump(response_body, f)
      f.close()

   return redirect(url_for("index"), code=302)

def get_spotify_client(sessionid):
   if environment == "production":
      return spotipy.Spotify(
            auth_manager=SpotifyOAuth(client_id=keys.SpotifyClientId[0],
               client_secret=keys.SpotifyClientSecret[0],
               redirect_uri=keys.RedirectUri[0],
               scope=scope,
               cache_handler=SqlCacheHandler(sessionid)
            )
         )
   else:
      return spotipy.Spotify(
            auth_manager=SpotifyOAuth(client_id=keys.SpotifyClientId[0],
               client_secret=keys.SpotifyClientSecret[0],
               redirect_uri=keys.RedirectUri[0],
               scope=scope
            )
         )

if __name__ == '__main__':
   if environment == "production":
      app.run()
   else:
      app.run(ssl_context='adhoc')