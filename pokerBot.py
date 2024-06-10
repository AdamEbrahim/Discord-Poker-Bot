import os
import discord
import asyncio
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import pymongo.errors
import utilities
import sys

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
outstanding_payments_collection = db.outstanding_payments #create a new "outstanding_payments" collection (table) in discordBot database if doesn't exist

try:
    outstanding_payments_collection.create_index({"debtor": 1, "recipient": 1}, unique=True)
except pymongo.errors.PyMongoError as e:
    print(f"An error occurred while creating the unique index in outstanding_payments_collection: {e}")


#--ERROR HANDLING--#

#general uncaught bot error handler
@bot.event
async def on_error(event, *args):
    print(f'Uncaught Error: {event}')
    print(sys.exc_info())

#general uncaught command error handler
@bot.event
async def on_command_error(ctx, error):
    print(f'Uncaught Command Error: {error}')


#--DATABASE OPERATION WRAPPERS--#

#implements insert if non-existant entry or update if entry exists 
async def create_users_entry(discord_id, username):
    try:
        user_entry = {"_id": discord_id, "venmo_usr": username}
        users_collection.insert_one(user_entry)
        return True
    except pymongo.errors.DuplicateKeyError as e: #entry exists
        print(f"Duplicate key error in create_users_entry, updating entry instead")
        users_collection.update_one({"_id": discord_id}, {"$set": {"venmo_usr": username}})
        return True
    except Exception as e:
        print(f"Unknown error in create_users_entry: {e}")
        return False


#implements insert if non-existant entry or update if entry exists 
async def create_outstanding_payments_entry(discord_id_debtor: int, discord_id_recipient: int, amount: float):
    if not (isinstance(discord_id_debtor, int) and isinstance(discord_id_recipient, int) and isinstance(amount, (int, float))):
        print("create_outstanding_payments_entry parameters are incorrect types")
        return False
    
    try:
        #fields: discord id of person who owes money, discord id of person to whom money is owed (can't be their venmo since it can change in users table), amount
        outstanding_payments_entry = {"debtor": discord_id_debtor, "recipient": discord_id_recipient, "amount": amount}
        outstanding_payments_collection.insert_one(outstanding_payments_entry); 
        return True
    except pymongo.errors.DuplicateKeyError as e: #entry exists (outstanding balance to person exists, increase outstanding balance)
        print(f"Duplicate key error in create_outstanding_payments_entry, updating entry instead")
        outstanding_payments_collection.update_one({"debtor": discord_id_debtor, "recipient": discord_id_recipient}, {"$inc": {"amount": amount}})
        return True
    except Exception as e:
        print(f"Unknown error in create_outstanding_payments_entry: {e}")
        return False


async def get_outstanding_payments_entries(discord_id):
    try:
        result = outstanding_payments_collection.aggregate([
            {'$match': {'debtor': discord_id}},
            {
                '$lookup': 
                {
                    "from": "users",
                    "localField": "recipient",
                    "foreignField": "_id",
                    "as": "results"
                }
            }
        ])

        return result

    except Exception as e:
        print(f"Unknown error in get_outstanding_payments_entries: {e}")
        return None


#--EVENTS--#
@bot.event
async def on_ready():
    #await bot.tree.sync(guild=discord.Object(id=1246667177759608932))
    print(f'{bot.user.name} has connected to Discord!')


async def get_venmo_user(member, channel, interaction, hasRespondedInteraction):
    try:
        embed = discord.Embed(title=f'Please send your Venmo username (the name after the \"@\").',
                                    description='Please make sure it is accurate so that you can receive your Poker winnings. This message will time out in 2 minutes.',
                                    color=0x800080)
        
        if hasRespondedInteraction:
            await channel.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)

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
              

@bot.tree.command(name='verify-venmo', description="Connect your Venmo username to your account to receive future Poker earnings", guild=discord.Object(id=1246667177759608932))
@app_commands.describe(username='Your Venmo username (the name after the \"@\")')
@commands.max_concurrency(number=1, per=commands.BucketType.user, wait=False) #Ensures command can only be used 1 time per user concurrently
async def verify_venmo_cmd(interaction, username: str):
    # hasRespondedInteraction = False

    # if await utilities.can_dm_user(interaction.user):
    #     if interaction.channel != interaction.user.dm_channel:
    #         await interaction.response.send_message(f'{interaction.user.mention} Please check dms!')
    #         hasRespondedInteraction = True

    #     channel = interaction.user.dm_channel
    # else:
    #     channel = interaction.channel

    # username = await get_venmo_user(interaction.user, channel, interaction, hasRespondedInteraction)

    if username != None:
        if await create_users_entry(interaction.user.id, username) == True:
            embed = discord.Embed(title= f'✅ Your Venmo account has been confirmed, {interaction.user.name}. Thank you!', description=f'Your username has been recorded as \"**@{username}**\".', color=0x00ff00)
        else:
            embed = discord.Embed(title= f'❌ Error in confirming Venmo account for {interaction.user.name}. Please try again.', color=0xf50000)
        
        await interaction.response.send_message(embed=embed)


@bot.tree.command(name="record-game", description='Record player winnings from a Poker game', guild=discord.Object(id=1246667177759608932))
@commands.max_concurrency(number=1, per=commands.BucketType.user, wait=False) #Ensures command can only be used 1 time per user concurrently
async def record_game_cmd(interaction):
    await create_outstanding_payments_entry(1234, 5678, 32.5)
    await create_outstanding_payments_entry(1357, 2468, 17.8)
    await create_outstanding_payments_entry(1357, 3579, 23.3)
    await create_outstanding_payments_entry(1357, 3579, 15.5)
    await create_outstanding_payments_entry(9872, 1627, 12)
    

@bot.tree.command(name="payout", description='Send Venmo requests for all outstanding balances a user(s) has', guild=discord.Object(id=1246667177759608932))
async def payout_cmd(interaction):
    await create_users_entry(3579, "Anotha_one")
    entries = await get_outstanding_payments_entries(1357)

    count = 0
    for item in entries:
        venmo_info = item['results']

        if len(venmo_info) < 1:
            print("Error: Recipients venmo account info was not found")
        else:
            paymentURL = f"https://venmo.com?url=venmo://paycharge?txn=pay&recipients=@{venmo_info[0]['venmo_usr']}&amount={item['amount']}"
            embed = discord.Embed(title= f"Payment of **${item['amount']}** to **@{venmo_info[0]['venmo_usr']}**.", description=paymentURL, color=0x00ff00)

            if count == 0:
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.channel.send(embed=embed)
            count = count + 1

    if count == 0: #no entries returned
        embed = discord.Embed(title= f'❌ No required payouts found for **{interaction.user.name}**.', color=0xf50000)
        await interaction.response.send_message(embed=embed)



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

# @bot.command(name='test', help='Hi')
# async def test(ctx, one):
#     print(type(ctx))
#     print(ctx)

#--RUN--#
bot.run(DISCORD_TOKEN)