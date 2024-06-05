import os
import discord
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import pymongo.errors
import utilities

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_CLUSTER_STRING = os.getenv('DB_CLUSTER_STRING')

#default intents with members enabled
intents = discord.Intents.default()
intents.members = True #now needs privileged intents enabled for members
intents.message_content = True

#create bot object to interact with discord API 
bot = commands.Bot(command_prefix='/', intents=intents)


#--Connect to MongoDB database--#
db_url = f'mongodb+srv://{DB_USERNAME}:{DB_PASSWORD}@{DB_CLUSTER_STRING}'

# Create a new client and connect to the server
db_client = MongoClient(db_url, server_api=ServerApi('1'))
# Send a ping to confirm a successful connection
try:
    db_client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

db = db_client.discordBot #create a new database in cluster called "discordBot" if does not exist
users_collection = db.users #create a new "users" collection (table) in discordBot database if doesn't exist
#users_collection.insert_one({"_id": "109413", "key_test":"val_test2"})

#--ERROR HANDLING--#

#general uncaught error handler
@bot.event
async def on_error(event, *args):
    print(f'Uncaught Error: {event}')

#general uncaught command error handler
@bot.event
async def on_command_error(ctx, error):
    print(f'Uncaught Command Error: {error}')


#--DATABASE OPERATION WRAPPERS--#

#implements insert if non-existant entry or update if entry exists 
async def create_users_entry(ctx, username):
    try:
        if users_collection.find_one({"_id": ctx.author.id}) != None: #exists in database, update
            users_collection.update_one({"_id": ctx.author.id}, {"$set": {"venmo_usr": username}})
        else: #does not exist in database, create new entry
            user_entry = {"_id": ctx.author.id, "venmo_usr": username}
            users_collection.insert_one(user_entry)
    except pymongo.errors.DuplicateKeyError as e:
        print(f"Somehow duplicate key error in create_users_entry: {e}")
    except Exception as e:
        print(f"Unknown error in create_users_entry: {e}")


#implements insert if non-existant entry or update if entry exists 
async def create_outstanding_payments_entry():
    print("hi")


#--EVENTS--#
@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


async def get_venmo_user(member, channel):
    try:
        embed = discord.Embed(title=f'Please send your Venmo username (the name after the \"@\").',
                                    description='Please make sure it is accurate so that you can receive your Poker winnings. This message will time out in 2 minutes.',
                                    color=0x800080)
        await channel.send(embed=embed)

    except Exception as e:
        print(f"Error while sending message to get user's Venmo account: {e}")
    
    def check(msg):
        return msg.channel == channel and msg.author == member
    
    def check2(reaction, user):
        return user == member and (str(reaction.emoji) == '❌' or str(reaction.emoji) == '✅')
    
    verified = False
    while not verified:
        try:
            username = await bot.wait_for('message', timeout=30.0, check=check) #2 minute time out
        except asyncio.TimeoutError:
            embed = discord.Embed(title='TIMEOUT OCCURRED 👎', description='Please use the \"**/verify-venmo**\" command to try again.', color=0xf50000)
            await channel.send(embed=embed)
            return None

        embed = discord.Embed(title='CONFIRMATION', description=f'Please confirm that your venmo username is \"**@{username.content}**\". This will time out in 2 minutes.', color=0x800080)
        confirmation_msg = await channel.send(embed=embed)
        await confirmation_msg.add_reaction('❌')
        await confirmation_msg.add_reaction('✅')

        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=120.0, check=check2)
        except asyncio.TimeoutError:
            embed = discord.Embed(title='TIMEOUT OCCURRED 👎', description='Please use the \"**/verify-venmo**\" command to try again.', color=0xf50000)
            await channel.send(embed=embed)
            return None
        else:
            if str(reaction.emoji) == '❌':
                embed = discord.Embed(title='Please resend your Venmo username (the name after the \"@\").',
                                 description='This message will time out in 2 minutes.',
                                 color=0xf50000)
                await channel.send(embed=embed)
                
            elif str(reaction.emoji) == '✅':
                await confirmation_msg.delete()
                verified = True

            else:
                embed = discord.Embed(title='UNKNOWN ERROR 👎', description='Please use the \"**/verify-venmo**\" command to try again.', color=0xf50000)
                await channel.send(embed=embed)
                return None

    #Now they must be verified
    return username.content #return input venmo username


@bot.event
async def on_member_join(member):
    if await utilities.can_dm_user(member):
        await member.dm_channel.send(f'Hey {member.name}! Please use the \"**/verify-venmo**\" command if you want to connect your Venmo username to your account to receive future Poker earnings.')
        

@bot.command(name='verify-venmo', help='Use this command to connect your Venmo username to your account to receive future Poker earnings.')
@commands.max_concurrency(number=1, per=commands.BucketType.user, wait=False) #Ensures command can only be used 1 time per user concurrently
async def verify_venmo_cmd(ctx):
    if await utilities.can_dm_user(ctx.author):
        if ctx.channel != ctx.author.dm_channel:
            await ctx.channel.send(f'{ctx.author.mention} Please check dms!')

        channel = ctx.author.dm_channel
    else:
        channel = ctx.channel

    username = await get_venmo_user(ctx.author, channel)

    if username != None:
        await create_users_entry(ctx, username)
        embed = discord.Embed(title= f'Your Venmo account confirmed has been confirmed, {ctx.author.name}. Thank you!', color=0x00ff00)
        await channel.send(embed=embed)
    


# @bot.event
# async def on_raw_member_remove(payload):



#Overriding the default provided on_message() forbids extra commands from running without the 'await bot.process_commands(message)'
# @bot.event
# async def on_message(message):
#     await bot.process_commands(message)

#     if message.author == bot.user:
#         return
#     else:
#         print(type(message))
#         print(message.content)


# @bot.command(name='', help='')
# @commands.has_permissions

@bot.command(name='test', help='Hi')
async def test(ctx, one):
    print(type(ctx))
    print(ctx)

#--RUN--#
bot.run(DISCORD_TOKEN)