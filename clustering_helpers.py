__all__ = ['get_all_items_in_all_playlists', 'get_audio_features_for_tracks', 'get_selected_features', 'get_all_items_for_playlist']

import pandas as pd
import numpy as np
import spotipy

def get_all_items_for_playlist(playlist_id, spotify_client):
    playlist = spotify_client.playlist(playlist_id)
    tracks = pd.DataFrame(playlist['tracks']['items'])
    print(tracks.track.head())
    id = tracks.apply(lambda x: x.track['id'], axis=1)
    track_names = tracks.apply(lambda x: x.track['name'], axis=1)
    track_primary_artist = tracks.apply(lambda x: x.track['artists'][0]['name'], axis=1)
    is_track = tracks.apply(lambda x: x.track['type'] == 'track', axis=1)
    playlist_name = playlist['name']
    all_items = pd.DataFrame(
            [id, track_names, track_primary_artist, pd.Series(np.repeat(playlist_name, is_track.shape[0])), is_track]).transpose()

    all_items.columns = ['id','song','artist', 'playlist', 'is_track']
    return all_items


def get_all_items_in_all_playlists(spotify_client):
    user_playlists = pd.DataFrame(spotify_client.current_user_playlists(limit=50, offset=0)['items'])
    all_items = pd.DataFrame()
    
    for playlist in user_playlists['id']:
        tracks = pd.DataFrame(spotify_client.playlist(playlist)['tracks']['items'])
        id = tracks.apply(lambda x: x.track['id'], axis=1)
        track_names = tracks.apply(lambda x: x.track['name'], axis=1)
        track_primary_artist = tracks.apply(lambda x: x.track['artists'][0]['name'], axis=1)
        is_track = tracks.apply(lambda x: x.track['type'] == 'track', axis=1)
        playlist_name = user_playlists[user_playlists['id'] == playlist]['name'].iloc[0]
        all_items = pd.concat([all_items, pd.DataFrame(
            [id, track_names, track_primary_artist, pd.Series(np.repeat(playlist_name, is_track.shape[0])), is_track])
                               .transpose()])
        
    all_items.columns = ['id','song','artist', 'playlist', 'is_track']
    return all_items

def get_audio_features_for_tracks(ids, spotify_client):
    ids = pd.Series(ids.unique())
    page = 100
    features = pd.DataFrame()
    
    while page < ids.shape[0]:
        features = pd.concat([features, pd.DataFrame(spotify_client.audio_features(ids[(page-100):page]))])
        page += 100
        
    if page == ids.shape[0]:
        return features
    
    features = pd.concat([features, pd.DataFrame(spotify_client.audio_features(ids[(page-100):ids.shape[0]]))])
    
    return features 

def get_selected_features(request):
    features = []

    if request.args.get('include-danceability', type=bool):
        features += ['danceability']
    if request.args.get('include-energy', type=bool):
        features += ['energy']
    if request.args.get('include-key', type=bool):
        features += ['key']
    if request.args.get('include-loudness', type=bool):
        features += ['loudness']
    if request.args.get('include-mode', type=bool):
        features += ['mode']
    if request.args.get('include-speechiness', type=bool):
        features += ['speechiness']
    if request.args.get('include-acousticness', type=bool):
        features += ['acousticness']
    if request.args.get('include-instrumentalness', type=bool):
        features += ['instrumentalness']
    if request.args.get('include-liveness', type=bool):
        features += ['liveness']
    if request.args.get('include-valence', type=bool):
        features += ['liveness']
    if request.args.get('include-tempo', type=bool):
        features += ['liveness']
    if request.args.get('include-time-signature', type=bool):
        features += ['time_signature']
    if request.args.get('include-duration', type=bool):
        features += ['duration_ms']

    if len(features) > 0:
        return features
    
    return None

