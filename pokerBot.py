import os
import discord
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

#default intents with members enabled
intents = discord.Intents.default()
intents.members = True

#create bot client object to interact with discord API 
client = discord.Client(intents=intents)

#--EVENTS--#
@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

#--RUN--#
client.run(DISCORD_TOKEN)