__all__ = ['clean_lyrics', 'grey_color_func']

import re
import random

def clean_lyrics(lyrics):
    if lyrics.startswith("1.") or " - " in lyrics:
        return ""

    lyrics = re.sub(r'[0-9]+[a-zA-Z]+', '', lyrics)
    lyrics = re.sub(r'[a-zA-Z]+[0-9]+', '', lyrics)
    
    return (lyrics
        .replace(",", "")
        .lower()
        .replace("\n", " ")
        .replace("\u2005", " ")
        .replace("urlcopyembedcopy", "")
        .replace("embedshare", "")
        .replace(" i ", " I ")
        .replace("i'm", "I'm")
        .replace("i've", "I've")
        .replace("i'll", "I'll")
        .replace("(", "")
        .replace(")", "")
    )

def grey_color_func(word, font_size, position, orientation, random_state=None,
                    **kwargs):
    return f"hsl({random.randint(170, 210)}, 100%, {random.randint(10, 100)}%)"