import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.members = True 
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

# Event listener for when the bot is ready
@bot.event
async def on_ready():
    print(f'Bot is online as {bot.user}')

# Command to get the user ID
@bot.command()
async def get_user_id(ctx, user: discord.User):
    await ctx.send(f'The user ID of {user.name} is {user.id}')

# Event listener for message events
# @bot.event
# async def on_message(message):
#     if isinstance(message.channel, discord.DMChannel):
#         print(f"Received a direct message from {message.author}: {message.content}")
#     await bot.process_commands(message)


bot.run(DISCORD_TOKEN)