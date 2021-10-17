import requests
import spotipy
import pandas as pd
from spotipy import cache_handler
import numpy as np
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.oauth2 import SpotifyOAuth, CacheHandler
import lyricsgenius
import json
import uuid
import time
from os.path import exists
import urllib

# General libraries.
import re
import numpy as np
import pandas as pd

from flask import Flask, make_response, request, redirect
app = Flask(__name__)

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
          "scope": "user-read-recently-played"
       }
       print("https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(data))
       return redirect("https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(data), code=302)
    return "success"

@app.route('/')
def index():
   authorization = authorize(request)
   if(authorization != "success"):
      return authorization

   keys = pd.read_csv("keys.csv")
   sessionid = request.cookies.get("ReflectifySession")

   if(sessionid == None):
      return make_response("Missing sessionid.")

   print("User (" + str(sessionid) + ")")
   sp = spotipy.Spotify(
      auth_manager=SpotifyOAuth(client_id=keys.SpotifyClientId[0],
      client_secret=keys.SpotifyClientSecret[0],
      redirect_uri=keys.RedirectUri[0],
      scope="user-read-recently-played",
      username=sessionid)
   )
   return str(sp.current_user_recently_played())

@app.route("/login/success")
def close_me():
   return "You can close this tab!"

@app.route('/login')
def login():
   ## NEXT STEPS: I NEED TO IMPLEMENT A SYSTEM TO GET an access token,
   ## cache it with the unique sessionid, then retrieve it. 
   keys = pd.read_csv("keys.csv")
   sessionid = request.cookies.get("ReflectifySession")
   print("session id: " + str(sessionid))

   if(sessionid == None):
      print("Making a new sessionid")
      response = make_response(redirect("https://127.0.0.1:5000", code=302))
      session = uuid.uuid4()
      response.set_cookie("ReflectifySession", str(session))
      return response
      
   return redirect("https://127.0.0.1:5000", code=302)

   # genius = lyricsgenius.Genius(keys.GeniusClientAccessToken[0])

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