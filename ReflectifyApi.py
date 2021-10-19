import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json
import uuid
import time
from os.path import exists
import urllib
import numpy as np
import pandas as pd
import lyricsgenius

from flask import Flask, make_response, request, redirect, render_template
app = Flask(__name__)

scope = "user-read-recently-played user-read-private user-read-email"

def authorize(request):
    keys = pd.read_csv("keys.csv")
    sessionid = request.cookies.get("ReflectifySession")

    if(sessionid == None):
       return redirect("https://127.0.0.1:5000/login", code=302)

    if(not exists(".cache-" + str(sessionid))):
       data = {
          "response_type": "code",
          "redirect_uri": keys.RedirectUri[0],
          "client_id": keys.SpotifyClientId[0],
          "scope": scope
       }
       return redirect("https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(data), code=302)
    
    return "success"

@app.route('/')
def index():
   authorization = authorize(request)
   if(authorization != "success"):
      return render_template('index.html')

   keys = pd.read_csv("keys.csv")
   sessionid = request.cookies.get("ReflectifySession")

   sp = spotipy.Spotify(
      auth_manager=SpotifyOAuth(client_id=keys.SpotifyClientId[0],
      client_secret=keys.SpotifyClientSecret[0],
      redirect_uri=keys.RedirectUri[0],
      scope=scope,
      username=sessionid)
   )
   
   return render_template('index.html', username=sp.me()['display_name'])

@app.route('/recentlyplayed')
def recently_played():
   authorization = authorize(request)
   if(authorization != "success"):
      return authorization

   keys = pd.read_csv("keys.csv")
   sessionid = request.cookies.get("ReflectifySession")
   count = request.args.get("count")

   if(count == None or int(count) < 1 or int(count) > 50):
      count = 20

   sp = spotipy.Spotify(
      auth_manager=SpotifyOAuth(client_id=keys.SpotifyClientId[0],
      client_secret=keys.SpotifyClientSecret[0],
      redirect_uri=keys.RedirectUri[0],
      scope="user-read-recently-played",
      username=sessionid)
   )

   return render_template("recently_played.html", songs=sp.current_user_recently_played(int(count))['items'])

@app.route("/lyrics")
def lyrics():
   song_name = request.args.get("song")
   artist = request.args.get("artist")

   if(song_name == None):
      return "No song specified"

   if(artist == None):
      return "No artist specified"

   keys = pd.read_csv("keys.csv")
   genius = lyricsgenius.Genius(keys.GeniusClientAccessToken[0])
   song = genius.search_song(song_name, artist)
   return render_template("lyrics.html", lyrics=song.lyrics.split("\n"))

@app.route('/login')
def login(): 
   sessionid = request.cookies.get("ReflectifySession")
   print("session id: " + str(sessionid))

   if(sessionid == None):
      print("Making a new sessionid")
      response = make_response(redirect("https://127.0.0.1:5000", code=302))
      session = uuid.uuid4()
      response.set_cookie("ReflectifySession", str(session))
      return response
   
   authorization = authorize(request)
   if(authorization != "success"):
      return authorization

   return redirect("https://127.0.0.1:5000", code=302)

@app.route('/auth')
def auth():
   sessionid = request.cookies.get("ReflectifySession")
   code = request.args.get("code")
   print("Setting Auth code (" + str(code) + ") for user " + str(sessionid) + ".")
   keys = pd.read_csv("keys.csv")
   
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

   with open('.cache-' + str(sessionid), 'w') as outfile:
      json.dump(response_body, outfile)   
   return redirect("https://127.0.0.1:5000", code=302)

if __name__ == '__main__':
   app.run(ssl_context='adhoc')