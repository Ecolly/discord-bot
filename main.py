from typing import Final
import os
import discord
from dotenv import load_dotenv
from discord import Intents, Client, Message
from discord.ext import commands
import asyncio
import yt_dlp
from response import get_response
from dataclasses import dataclass
import re
import random
from datetime import timedelta


#Load token, load the private token
load_dotenv()
TOKEN:Final[str] = os.getenv("DISCORD_TOKEN")


# Bot Setup
intents = discord.Intents.default()
#intents are a way of specifying which types of events or information your bot wants to receive from Discord's servers.
intents.message_content = True
#commands.Bot is a subcass of client

client = commands.Bot(command_prefix= "!", intents=intents)

# Message functionality
# async programming - allows you to run tasks that may take some time, without blocking the execution of the rest of the program
# pause execution to wait for external task to complete

#given a user's message, respond to it
# async def send_message(message:Message)->None:
#     user_message = message.content
#     if not user_message:
#         print("Message was empty, maybe the intent to read discord message was disabled")
#         return
#     #walrus operation:  assign a value to a variable and evaluate it within an expression.
#     #in this case, check if user_message start with ? and then evaluate to true or false, then assign it to if statement
#     if is_private := user_message[0] =='?':
#         user_message = user_message[1:]
        
#     #await: pause the execution of async function until awaitable completes, this can only used in async function
#     try:
#         #get the corresponding response depending on user message
#         response: str = get_response(user_message)
#         #if its private, send it to user, if it not private send it to the server
#         if is_private:
#             await message.author.send(response)
#         else:
#             await message.channel.send(response)
#     except Exception as e:
#         print(e)
        
@client.event
#register a function as an event listener for a specific event trigger 
async def on_ready()->None:
    print(f'{client.user} is now running')


############################# Youtube bot settings #########################

def seconds_to_hms_with_timedelta(seconds):
    return str(timedelta(seconds=seconds))
@dataclass
class SongProperty:
    title:str #get the title of the song
    song:any #get the url to the google drive link of the mp3
    duration: int
    
server_list = {}
#youtube discord bot section
# dictionary {serverid : voice_client} - to keep track of servers joined by discord bot
voice_clients = {}
#dictionary {serverid: queue}
server_song_queues = {}
#options for yt_dlp (Youtube downloading library - extract/play audio from youtube)
yt_dl_options = {
    "format": "bestaudio/best"
}
ytdl = yt_dlp.YoutubeDL(yt_dl_options)
#options for ffmeg
#-vn means no video and disable video processsing we are only interested in the audio
ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
                  'options': '-vn -filter:a "volume=0.5, lowpass=f=15000"'}

#tracks the current song
is_playing = {}
preloaded_songs = {}
current_song = {}
loop_toggle = {}
loop_queue_toggle = {}

# check oncoming messages and make sure it fulfills requirements

# @client.event
# async def on_message(message: Message)-> None:
#     #make sure bot doesn't respond to itself
#     if message.author == client.user:
#         return

#     user_name = message.author #get the user's name
#     user_message = message.content #get the user's message
#     channel = message.channel #get the channel where the message came from

#plays the song
async def playsong(ctx:commands.Context, song_info:SongProperty):
    #user who provided the command
    user = ctx.author
    channel = ctx.channel
    try:
        # Ensure the bot is connected to the user's voice channel
        if ctx.guild.id not in voice_clients:
            # If not connected, connect to the user's voice channel
            voice_client = await user.voice.channel.connect()
            voice_clients[ctx.guild.id] = voice_client
        else:
            # Retrieve the existing voice client
            voice_client = voice_clients[ctx.guild.id]
            
        player = discord.FFmpegOpusAudio(song_info.song, **ffmpeg_options)
        await channel.send(f"Now playing {song_info.title}")
        
        
        def after_callback(error):
            if ctx.guild.id in voice_clients and voice_clients[ctx.guild.id].is_connected():
                asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop)
            else:
                print("Bot is no longer connected. Skipping play_next.")
        voice_client.play(player, after=after_callback)
        is_playing[ctx.guild.id] = True
    except Exception as e:
        print(e)

#plays the next song 
async def play_next(ctx: commands.Context):
    if ctx.guild.id not in voice_clients or not voice_clients[ctx.guild.id].is_connected():
        # Bot is no longer connected
        is_playing[ctx.guild.id] = False
        return
    if ctx.guild.id in loop_toggle and loop_toggle[ctx.guild.id]:
        # If looping is enabled, re-add the current song to the queue
        server_song_queues[ctx.guild.id].insert(0, current_song[ctx.guild.id])
    if ctx.guild.id in loop_queue_toggle and loop_queue_toggle[ctx.guild.id]:
        # If loop queue is enable, always add the current song to the back of the queue for looping
        server_song_queues[ctx.guild.id].append(current_song[ctx.guild.id])
    if server_song_queues[ctx.guild.id]:
        song = server_song_queues[ctx.guild.id].pop(0)
        current_song[ctx.guild.id] = song
        await playsong(ctx, song)
    else:
        is_playing[ctx.guild.id] = False
        await ctx.send("End of queue.")
        
async def get_playlist_item_count(ctx:commands.Context, playlist_url):
    try:
        # Use yt-dlp to fetch only playlist metadata without downloading
        ytdl_options = {
            "extract_flat": True,
            "skip_download": True  # Ensure no downloads occur
        }
        print(f"GET PLAYLIST INFO")
        #this part is done twice in case the user is in a specific song in the playlist, it will grab the ID, get the link to the actual playlist
        with yt_dlp.YoutubeDL(ytdl_options) as ytdl:
            info = ytdl.extract_info(playlist_url, download=False)  # Fetch playlist info
        play_list_url = f"https://www.youtube.com/playlist?list={info['id']}"
        with yt_dlp.YoutubeDL(ytdl_options) as ytdl:
            info = ytdl.extract_info(play_list_url, download=False)  # Fetch playlist info
        
        
        if "_type" in info and info["_type"] == "playlist":
            if "entries" in info:
                # Extract all individual video URLs
                for entry in info["entries"]:
                    if "url" in entry:
                        #see play function
                        await play(ctx, query=entry["url"])
            else:
                print("No entries found in the playlist.")
            return info.get("playlist_count", 0)  # Return the number of items in the playlist
        else:
            print("The provided URL is not a playlist.")
            return 0
    except Exception as e:
        print(f"Error fetching playlist info: {e}")
        return 0
        
# play command:
# if there's no queue, add the song to the queue + play the current song, if there's a queue, add the song to the queue

@client.command(name="play")
# * grabs everything after the keyword
async def play(ctx:commands.Context, *, query: str):
    try:
        if ctx.guild.id not in server_song_queues:
            server_song_queues[ctx.guild.id] = []
            current_song[ctx.guild.id] = "None"
            is_playing[ctx.guild.id] = False
            loop_toggle[ctx.guild.id] = False
        
        #youtube regex for matching key component
        youtube_url_regex = r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/(watch\?v=|embed/|v/)?[\w-]+'
        playlist_regex = r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/(playlist\?|.*?list=)[\w-]+'

        if re.match(playlist_regex, query): #if it matches to a playlist regex, then it will be dealt with differently
            link = query            #check how many songs are in the query, iterative get one by one and append to server playlist
            asyncio.run_coroutine_threadsafe(get_playlist_item_count(ctx, link), client.loop) 
        if re.match(youtube_url_regex, query):  # If matches, the user provided a link
            link = query
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL({"format": "bestaudio/best"}) as ytdl:
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(link, download=False))    
        else:  # Otherwise, treat it as a search phrase
            await ctx.send(f"Searching YouTube for: {query}")
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL({"format": "bestaudio/best"}) as ytdl:
                result = await loop.run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch:{query}", download=False))
                if result and "entries" in result and len(result["entries"]) > 0:
                    data = result["entries"][0]  # Take the first result
                    print(result)
                    #print(data)
                    link = data["url"]
                    youtube_id = data["id"]
                    youtube_link = f"https://www.youtube.com/watch?v={youtube_id}"
                    await ctx.send(f"Found: {data['title']}{youtube_link}")
                else:
                    await ctx.send("No results found on YouTube.")
                    return
        # Use yt-dlp to get metadata, the metadata put into ffmpeg to get the song    
        title = data["title"]
        url = data["url"]
        duration = data["duration"]
        print(f"THIS IS THE URL {url}")
        server_song_queues[ctx.guild.id].append(SongProperty(title, url, duration))
        await ctx.send(f"{title} added to queue")
        if not is_playing[ctx.guild.id]:
            await playcongif(ctx)
    except Exception as e:
        print(e)
        
async def playcongif(ctx:commands.Context):
    user = ctx.author
        # Ensure the bot is connected to the user's voice channel
    if ctx.guild.id not in voice_clients:
        # If not connected, connect to the user's voice channel
        voice_client = await user.voice.channel.connect()
        voice_clients[ctx.guild.id] = voice_client
    else:
        # Retrieve the existing voice client
        voice_client = voice_clients[ctx.guild.id]
    #if there bot is not playing, then play the song
    if not is_playing[ctx.guild.id]:
        is_playing[ctx.guild.id] = True
        await play_next(ctx)
        
#user inputs pause command
@client.command(name="pause")
async def pause(ctx:commands.Context):  
    try:
        voice_clients[ctx.guild.id].pause()
    except Exception as e:
        await ctx.send("uh oh I can't pause") 
        print(e)
#user input resume commmand
@client.command(name="resume")
async def resume(ctx:commands.Context):      
    try:
        voice_clients[ctx.guild.id].resume()
    except Exception as e:
        await ctx.send("uh oh I can't resume") 
        print(e)
#user input leave command
@client.command(name="leave")
async def leave(ctx:commands.Context): 
    try:
        voice_clients[ctx.guild.id].stop()
        await voice_clients[ctx.guild.id].disconnect()
        del voice_clients[ctx.guild.id]
        is_playing[ctx.guild.id] = False
        server_song_queues[ctx.guild.id] = []
        current_song[ctx.guild.id] = "None"
        loop_toggle[ctx.guild.id] = False
    except Exception as e:
        await ctx.send("uh oh I can't leave") 
        print(e)
    
    #await send_message(message, user_message)
@client.command(name="queue", aliases=["q"])
async def queue(ctx:commands.Context, page:int=1):
    #gives the command user the queue of the server
    queue_list = ""
    try:
        server_queue = server_song_queues.get(ctx.guild.id, [])
        if not server_queue:
            await ctx.send("The queue is currently empty.")
            return
        display_num = 10
        total_songs = len(server_queue)
        total_pages = (total_songs + display_num) //display_num
        
        if page < 1 or page > total_pages:
            await ctx.send(f"invalid page number. Please choose a page between 1 and {total_pages}.")
            return
        start_index = (page-1)*display_num
        end_index = min(start_index + display_num, total_songs)
        
        total_duration_seconds = sum(song.duration for song in server_queue)
        
        chunk = server_queue[start_index:end_index]
        queue_list = "\n".join(
            [f"{start_index + index + 1}. {song.title} [{seconds_to_hms_with_timedelta(song.duration)}]" for index, song in enumerate(chunk)]
        )
        # Check if the queue is empty
        if queue_list:
            await ctx.send(queue_list)  # Send the queue
            await ctx.send(f"Total time: {seconds_to_hms_with_timedelta(total_duration_seconds)}")
            if (total_pages>1):
                await ctx.send(f"Displaying songs {start_index+1} to {end_index}, Page {page} out of {total_pages}")
                
        else:
            await ctx.send("The queue is currently empty.")

    except KeyError:
        # Handle the case where there is no queue for the server
        await ctx.send("There is no song queue for this server.")

@client.command(name="skip")
async def skip(ctx: commands.Context):
    try:
        if ctx.guild.id not in voice_clients:
            await ctx.send("I'm not in the channel right now.")
            return
        voice_client = voice_clients[ctx.guild.id]
        if voice_client.is_playing():
            voice_client.stop()  # Stop the current song, triggering after_callback
            await ctx.send("Skipped the current song!")
        else:
            await ctx.send("There's no song currently playing.")
    except Exception as e:
        await ctx.send("An error occurred while skipping the song.")
        print(e)
@client.command(name="helpme")
async def help(ctx: commands.Context):
    try:
        await ctx.send(
        "Welcome to the Rhythm Rip Off\n"
        "**!play <url>** to play a song given a YouTube URL. Ex. **!play https://www.youtube.com/watch?...**\n"
        "**!play <phrase>** to search up a song on YouTube. Ex. **!play rick astley never gonna give you up**\n"
        "**!skip** to skip the current song\n"
        "**!queue** to see the queue, if there are multiple pages !queue <page number>\n"
        "**!shuffle** to shuffle the playlist\n"
        "**!pause** to pause the song\n"
        "**!resume** to resume the song\n"
        "**!leave** to boot the bot from the VC \n"
        "**!current** see the current song playing\n"
        "**!loop** loop the current song playing \n"
        "**!loopq** loop the queue\n"
        "**!remove <position> ** remove the song at position\n"
        "**!move <position x> <position y> ** move song from position x to position y\n"
    )
    except Exception as e:
        print(e)
@client.command(name = "shuffle")
async def shuffle(ctx: commands.Context):     
    random.shuffle(server_song_queues[ctx.guild.id])
    await ctx.send("queue shuffled")
#run the bot  
#TODO
@client.command(name = "loop")
async def loop(ctx: commands.Context):  
    #get the current song playing   
    if ctx.guild.id not in loop_toggle:
        loop_toggle[ctx.guild.id] = False  # Initialize if not already set
    
    loop_toggle[ctx.guild.id] = not loop_toggle[ctx.guild.id]  # Toggle the loop state
    
    if loop_toggle[ctx.guild.id]:
        await ctx.send("Looping is now **enabled**!")
    else:
        await ctx.send("Looping is now **disabled**.")

@client.command(name = "loopq")
async def loop_queue(ctx: commands.Context):  
    #get the current song playing   
    if ctx.guild.id not in loop_queue_toggle:
        loop_queue_toggle[ctx.guild.id] = False  # Initialize if not already set
    
    loop_queue_toggle[ctx.guild.id] = not loop_queue_toggle[ctx.guild.id]  # Toggle the loop state
    
    if loop_queue_toggle[ctx.guild.id]:
        await ctx.send("Looping queue is now **enabled**!")
    else:
        await ctx.send("Looping queue is now **disabled**.")
        
@client.command(name="remove", aliases=["r"])
async def remove(ctx:commands.Context, num: int):
    try:
        position = num-1
        
        if ctx.guild.id not in server_song_queues:
            await ctx.send("There is no queue available for server")
            return
        removed_song = server_song_queues[ctx.guild.id].pop(position)
        await ctx.send(f"Removed Song {removed_song.title}")
    except:
        await ctx.send(f"Cannot remove Song")
        
@client.command(name="move")
async def move(ctx:commands.Context, from_position:int, to_position:int):
    try:
        from_index = from_position - 1
        to_index = to_position - 1
        if ctx.guild.id not in server_song_queues:
            await ctx.send("There is no queue available for server")
            return
        queue = server_song_queues[ctx.guild.id]
        if from_index < 0 or from_index >= len(queue):
            await ctx.send(f"There is no song at queue position {from_index}")
            return
        if to_index < 0 or to_index >= len(queue):
            await ctx.send(f"position is beyong the position of the queue, valid positions are from 1 to {len(queue)+1}")
            return
        song = server_song_queues[ctx.guild.id].pop(from_index)  # Remove the song from the original position
        server_song_queues[ctx.guild.id].insert(to_index, song)
        await ctx.send(f"Moved **{song.title}** from position {from_position} to {to_position}.")
    except Exception as e:
         await ctx.send(f"An unexpected error occurred: {str(e)}")
@client.command(name = "current")
async def current(ctx: commands.Context):
    try:
        await ctx.send(f"{current_song[ctx.guild.id].title} [{seconds_to_hms_with_timedelta(current_song[ctx.guild.id].duration)}]")
    except Exception as e:
        print(e)
def main()->None:
    client.run(token = TOKEN)
    
if __name__ == '__main__':
    main()