import json
import os

import requests
import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from shazamio import Shazam
from urlextract import URLExtract
from pydub import AudioSegment

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_API_ID = int(os.environ.get('TELEGRAM_API_ID'))
TELEGRAM_API_HASH = os.environ.get('TELEGRAM_API_HASH')
INSTAGRAM_USERNAME = os.environ.get('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = os.environ.get('INSTAGRAM_PASSWORD')

bot = Client(
    "my_bot", bot_token=TELEGRAM_BOT_TOKEN,
    api_id=TELEGRAM_API_ID, api_hash=TELEGRAM_API_HASH
)
extractor = URLExtract()
shazam = Shazam()


def download_audio(link, filename):
    filepath = f'user_files/{filename}.%(ext)s'

    options = {
        'extract_audio': True,
        'audio_format': 'mp3',
        'outtmpl': filepath,
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    os.makedirs('user_files') if not os.path.exists('user_files') else None
    os.remove(filepath) if os.path.exists(filepath) else None

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(link, download=False)
        if info['extractor'].lower() == 'instagram':
            ydl.params['username'] = INSTAGRAM_USERNAME
            ydl.params['password'] = INSTAGRAM_PASSWORD

        ydl.download([link])
    return f'user_files/{filename}.mp3'


def cut_start(file_path):
    audio = AudioSegment.from_file(file_path)

    if len(audio) > 60000:
        start_time = len(audio)*0.07
        audio = audio[start_time:]

        audio.export(file_path, format="mp3")
    return file_path


async def recognize_song(file_path):
    out = await shazam.recognize_song(file_path)
    if not len(out['matches']):
        return None
    out = out['track']

    song_name = out['title']
    artist_name = out['subtitle']
    album_name = out['sections'][0]['metadata'][0]['text']
    release_year = out['sections'][0]['metadata'][2]['text']
    shazam_link = out['url']
    pfp = out['images']['coverart']

    shazam_youtube_link = None
    for entry in out['sections']:
        if 'youtubeurl' in entry:
            shazam_youtube_link = entry['youtubeurl']
            break
    response = requests.get(shazam_youtube_link)
    if response.status_code == 200:
        youtube_link = json.loads(response.text)["actions"][0]["uri"]
    else:
        youtube_link = None

    return {
        'song_name': song_name,
        'artist_name': artist_name,
        'album_name': album_name,
        'release_year': release_year,
        'shazam_link': shazam_link,
        'youtube_link': youtube_link,
        'pfp': pfp
    }


# noinspection PyUnusedLocal
@bot.on_message(filters.command("start"))
async def start_command(client, message):
    welcome_message = (
        "🎶 Welcome to the Music Recognition Bot! 🎶\n",
        "I can help you identify songs from audio links. Just send me any URL that contains audio,",
        "and I'll do my best to tell you the song's name, the artist,",
        "and provide links to the song on Shazam and YouTube if available.\n",
        "If you have any questions or feedback, feel free to reach out! (@FanaticExplorer)\n",
        "Let's discover some music together! 🚀"
    )
    await bot.send_message(message.from_user.id, "".join(welcome_message))


# noinspection PyUnusedLocal
@bot.on_message(filters.command("support"))
async def cmd_start(client, message):
    lines = (
        "Hey there!👋 \nI'm @FanaticExplorer, a student working on this bot.\n",
        "I haven't made any money from it yet, but I'm passionate about making it awesome for you! \n\n",
        "If you enjoy using @MusicRecognizeBot and would like to support its development, ",
        "here are a few ways you can contribute: \n\n",
        "🌐 Donate: Help cover costs and invest in improvements with a financial contribution. \n\n",
        "💬 Spread the Word: Share @MusicRecognizeBot with your friends and communities to help us grow.\n\n",
        "🌟 Feedback: Provide input to make this bot even better. Your thoughts mean a lot for me.\n\n",
        "🙏 Thanks for supporting my dream!"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Monobank Jar", url="https://send.monobank.ua/jar/9AvXq7doBs")],
            [InlineKeyboardButton("Ko-fi", url="https://ko-fi.com/fanaticexplorer")],
            [InlineKeyboardButton("Buy Me A Coffee", url="https://www.buymeacoffee.com/fanaticexplorer")]
        ]
    )
    await bot.send_message(message.from_user.id, "".join(lines), reply_markup=keyboard)


# noinspection PyUnusedLocal
@bot.on_message(filters.text)
async def text_handler(client, message):
    if not extractor.has_urls(message.text):
        return

    link = extractor.find_urls(message.text)[0]
    user_file_name = cut_start(download_audio(link, str(message.from_user.id)))
    result = await recognize_song(user_file_name)
    if not result:
        await bot.send_message(message.from_user.id, '🚫No matches found!')
        return

    # Creating an InlineKeyboardMarkup with buttons
    buttons = [
        [InlineKeyboardButton(text='Shazam Link', url=result['shazam_link'])]
    ]
    if result['youtube_link']:
        buttons.append([InlineKeyboardButton(text='Youtube Link', url=result['youtube_link'])])

    markup = InlineKeyboardMarkup(buttons)

    output_msg = (f"🎵 **Song:** {result['song_name']}\n"
                  f"🎤 **Artist:** {result['artist_name']}\n")
    if result['album_name']:
        output_msg += f"📀 **Album:** {result['album_name']}\n"
    if result['release_year']:
        output_msg += f"📅 **Year:** {result['release_year']}\n"

    await bot.send_photo(message.from_user.id, photo=result['pfp'], caption=output_msg, reply_markup=markup)

    os.remove(user_file_name) if os.path.exists(user_file_name) else None

bot.run()
