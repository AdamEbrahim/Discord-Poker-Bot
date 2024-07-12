import os
import discord
import asyncio
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import pymongo.client_session
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
    

async def get_users_entry(discord_id):
    try:
        result = users_collection.find_one({"_id": discord_id})
        return result
    except Exception as e:
        print(f"Unknown error in get_users_entry: {e}")
        return None



#implements insert if non-existant entry or update if entry exists, must pass in the session for ACID transaction (all or nothing)
async def create_outstanding_payments_entry(discord_id_debtor: int, discord_id_recipient: int, amount: float, session: pymongo.client_session.ClientSession):
    if not (isinstance(discord_id_debtor, int) and isinstance(discord_id_recipient, int) and isinstance(amount, (int, float)) and isinstance(session, pymongo.client_session.ClientSession)):
        print("create_outstanding_payments_entry parameters are incorrect types")
        raise TypeError("create_outstanding_payments_entry parameters are incorrect types")
    
    #fields: discord id of person who owes money, discord id of person to whom money is owed (can't be their venmo since it can change in users table), amount
    #outstanding_payments_entry = {"debtor": discord_id_debtor, "recipient": discord_id_recipient, "amount": amount}

    #upsert (insert if not present, update other wise)
    outstanding_payments_collection.update_one({"debtor": discord_id_debtor, "recipient": discord_id_recipient}, {"$inc": {"amount": amount}}, upsert=True, session=session)



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
    

async def delete_outstanding_payments_entry(discord_id_debtor, discord_id_recipient):
    try:
        res = outstanding_payments_collection.delete_one({"debtor": discord_id_debtor, "recipient": discord_id_recipient})
        if res == 0: #somehow unable to delete the document
            print("Unable to find outstanding payments entry to delete")
            return False
        else:
            return True
    except Exception as e:
        print(f"Uknown error in delete_outstanding_payments_entry: {e}")
        return False


#--EVENTS--#
@bot.event
async def on_ready():
    # await bot.tree.sync(guild=discord.Object(id=1246667177759608932))
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


@bot.tree.command(name="record-game-immediate-payout", description='Send 1-tap payment Venmo links to users after a Poker game.', guild=discord.Object(id=1246667177759608932))
@app_commands.describe(player1="Player name", player1_buy_in="Monetary value of the player's buy-in", player1_winnings="Monetary value of the player's remaining chips",
                       player2="Player name", player2_buy_in="Monetary value of the player's buy-in", player2_winnings="Monetary value of the player's remaining chips",
                       player3="Player name", player3_buy_in="Monetary value of the player's buy-in", player3_winnings="Monetary value of the player's remaining chips",
                       player4="Player name", player4_buy_in="Monetary value of the player's buy-in", player4_winnings="Monetary value of the player's remaining chips",
                       player5="Player name", player5_buy_in="Monetary value of the player's buy-in", player5_winnings="Monetary value of the player's remaining chips",
                       player6="Player name", player6_buy_in="Monetary value of the player's buy-in", player6_winnings="Monetary value of the player's remaining chips",
                       player7="Player name", player7_buy_in="Monetary value of the player's buy-in", player7_winnings="Monetary value of the player's remaining chips",
                       player8="Player name", player8_buy_in="Monetary value of the player's buy-in", player8_winnings="Monetary value of the player's remaining chips",)
async def immediate_payout_game_cmd(interaction, player1: discord.Member, player1_buy_in: float, player1_winnings: float,
                           player2: discord.Member = None, player2_buy_in: float = None, player2_winnings: float = None,
                           player3: discord.Member = None, player3_buy_in: float = None, player3_winnings: float = None,
                           player4: discord.Member = None, player4_buy_in: float = None, player4_winnings: float = None,
                           player5: discord.Member = None, player5_buy_in: float = None, player5_winnings: float = None,
                           player6: discord.Member = None, player6_buy_in: float = None, player6_winnings: float = None,
                           player7: discord.Member = None, player7_buy_in: float = None, player7_winnings: float = None,
                           player8: discord.Member = None, player8_buy_in: float = None, player8_winnings: float = None):
    
    maxParameters = 8
    data = [] # list of lists, where each list has the form [player_id, player_buy_in, player_winnings]

    distinctPlayers = set() # set to make sure no duplicate players
    unauthenticatedPlayers = [] #list of unauthenticated players
    for i in range(maxParameters): #Access all parameters easily, ensure all players have a corresponding buy in and winnings
        player = f"player{i+1}"
        playerBuyIn = f"player{i+1}_buy_in"
        playerWinnings = f"player{i+1}_winnings"

        #Get value of parameters passed in for player_i
        player = locals()[player]
        playerBuyIn = locals()[playerBuyIn]
        playerWinnings = locals()[playerWinnings]

        #error checking and putting in lists for passed parameters
        if player and playerBuyIn != None and playerWinnings != None: #if all are not None then valid [player, buy_in, winnings] entry
            if playerBuyIn < 0 or playerWinnings < 0: #no negative values
                embed = discord.Embed(title= f'❌ Invalid Arguments', description='Please make sure there are no negative values. A player who lost all chips would have a winnings value of 0.', color=0xf50000)
                await interaction.response.send_message(embed=embed)
                return
            elif await get_users_entry(player.id) == None: #at least one player is not authenticated, add to list so at end we can report all unauthenticated players
                unauthenticatedPlayers.append(player) #discord.member

            #no duplicate players
            if player.id in distinctPlayers:
                embed = discord.Embed(title= f'❌ No Duplicate Players', color=0xf50000)
                await interaction.response.send_message(embed=embed)
                return

            distinctPlayers.add(player.id)
            data.append([player.id, round(playerBuyIn, 2), round(playerWinnings, 2)]) #[player_id, player_buy_in, player_winnings]

        elif player or playerBuyIn != None or playerWinnings != None: #if above is false but at least 1 is not None, reply with error message
            embed = discord.Embed(title= f'❌ Invalid Arguments', description='Please make sure the player name, buy-in, and winnings are recorded for each submitted player.', color=0xf50000)
            await interaction.response.send_message(embed=embed)
            return


    #have unauthenticated players, tell user they cannot record a game if all players don't have Venmo verified
    if len(unauthenticatedPlayers) > 0:
            unverifiedUsers = ''
            for p in unauthenticatedPlayers:
                unverifiedUsers += f'{p.mention}, '

            embed = discord.Embed(title= f'❌ Unverified Players', description= f'Users: {unverifiedUsers}have not been verified. Please make sure all players have used the \"**/verify-venmo**\" command.', color=0xf50000)
            await interaction.response.send_message(embed=embed)
            return
    
    #Must have more than one player
    if len(data) <= 1:
        embed = discord.Embed(title= f'❌ Invalid Number of Players', description= f'You must have at least 2 players.', color=0xf50000)
        await interaction.response.send_message(embed=embed)
        return

    #if made it here that means no errors in parameters passed in, defer response while debt settlement algo runs
    await interaction.response.defer()

    #run poker debt settlement algo with error checking
    transactions = []
    try:
        transactions = utilities.poker_debt_settlement_algo(data)

        if transactions == None: #None returned if nonzero sum
            embed = discord.Embed(title= f'❌ Invalid Values', description= f'Please make sure the sum of player buy-ins equals the sum of player winnings.', color=0xf50000)
            await interaction.followup.send(embed=embed)

            print("Error in given arguments: Nonzero total sum")
            return

    except Exception as e:
        embed = discord.Embed(title= f'❌ Unknown Error', description= f'An unknown error has occurred in our algorithm. Please try again.', color=0xf50000)
        await interaction.followup.send(embed=embed)

        print(f"Error in poker debt settlement algorithm: {e}")
        return
    

    embed = discord.Embed(title= f'✅ Payment links are being sent out!', description="Links will be sent to DMs if authorized. Otherwise they will appear here.", color=0x00ff00)
    await interaction.followup.send(embed=embed)


    for transaction in transactions:
        venmo_usr = await get_users_entry(transaction[1]) #recipient venmo info
        venmo_usr = venmo_usr['venmo_usr']
        amount = format(transaction[2], '.2f')

        paymentURL = f"https://venmo.com?url=venmo://paycharge?txn=pay&recipients=@{venmo_usr}&amount={amount}&note=game"

        debtor = bot.get_user(transaction[0])

        if await utilities.can_dm_user(debtor):
            embed = discord.Embed(title= f"Payment of **${amount}** to **@{venmo_usr}**.", description=paymentURL, color=0x00ff00)
            await debtor.dm_channel.send(embed=embed)
        else:
            # await interaction.followup.send(f"{debtor.mention}")
            embed = discord.Embed(title= f"Payment of **${amount}** to **@{venmo_usr}**.", description=f"{debtor.mention}: {paymentURL}", color=0x00ff00)
            await interaction.followup.send(embed=embed)




@bot.tree.command(name="record-game", description='Record player winnings from a Poker game for future payment', guild=discord.Object(id=1246667177759608932))
@app_commands.describe(player1="Player name", player1_buy_in="Monetary value of the player's buy-in", player1_winnings="Monetary value of the player's remaining chips",
                       player2="Player name", player2_buy_in="Monetary value of the player's buy-in", player2_winnings="Monetary value of the player's remaining chips",
                       player3="Player name", player3_buy_in="Monetary value of the player's buy-in", player3_winnings="Monetary value of the player's remaining chips",
                       player4="Player name", player4_buy_in="Monetary value of the player's buy-in", player4_winnings="Monetary value of the player's remaining chips",
                       player5="Player name", player5_buy_in="Monetary value of the player's buy-in", player5_winnings="Monetary value of the player's remaining chips",
                       player6="Player name", player6_buy_in="Monetary value of the player's buy-in", player6_winnings="Monetary value of the player's remaining chips",
                       player7="Player name", player7_buy_in="Monetary value of the player's buy-in", player7_winnings="Monetary value of the player's remaining chips",
                       player8="Player name", player8_buy_in="Monetary value of the player's buy-in", player8_winnings="Monetary value of the player's remaining chips",)
async def record_game_cmd(interaction, player1: discord.Member, player1_buy_in: float, player1_winnings: float,
                           player2: discord.Member = None, player2_buy_in: float = None, player2_winnings: float = None,
                           player3: discord.Member = None, player3_buy_in: float = None, player3_winnings: float = None,
                           player4: discord.Member = None, player4_buy_in: float = None, player4_winnings: float = None,
                           player5: discord.Member = None, player5_buy_in: float = None, player5_winnings: float = None,
                           player6: discord.Member = None, player6_buy_in: float = None, player6_winnings: float = None,
                           player7: discord.Member = None, player7_buy_in: float = None, player7_winnings: float = None,
                           player8: discord.Member = None, player8_buy_in: float = None, player8_winnings: float = None):
    
    maxParameters = 8
    data = [] # list of lists, where each list has the form [player_id, player_buy_in, player_winnings]

    distinctPlayers = set() # set to make sure no duplicate players
    unauthenticatedPlayers = [] #list of unauthenticated players
    for i in range(maxParameters): #Access all parameters easily, ensure all players have a corresponding buy in and winnings
        player = f"player{i+1}"
        playerBuyIn = f"player{i+1}_buy_in"
        playerWinnings = f"player{i+1}_winnings"

        #Get value of parameters passed in for player_i
        player = locals()[player]
        playerBuyIn = locals()[playerBuyIn]
        playerWinnings = locals()[playerWinnings]

        #error checking and putting in lists for passed parameters
        if player and playerBuyIn != None and playerWinnings != None: #if all are not None then valid [player, buy_in, winnings] entry
            if playerBuyIn < 0 or playerWinnings < 0: #no negative values
                embed = discord.Embed(title= f'❌ Invalid Arguments', description='Please make sure there are no negative values. A player who lost all chips would have a winnings value of 0.', color=0xf50000)
                await interaction.response.send_message(embed=embed)
                return
            elif await get_users_entry(player.id) == None: #at least one player is not authenticated, add to list so at end we can report all unauthenticated players
                unauthenticatedPlayers.append(player) #discord.member

            #no duplicate players
            if player.id in distinctPlayers:
                embed = discord.Embed(title= f'❌ No Duplicate Players', color=0xf50000)
                await interaction.response.send_message(embed=embed)
                return

            distinctPlayers.add(player.id)
            data.append([player.id, round(playerBuyIn, 2), round(playerWinnings, 2)]) #[player_id, player_buy_in, player_winnings]

        elif player or playerBuyIn != None or playerWinnings != None: #if above is false but at least 1 is not None, reply with error message
            embed = discord.Embed(title= f'❌ Invalid Arguments', description='Please make sure the player name, buy-in, and winnings are recorded for each submitted player.', color=0xf50000)
            await interaction.response.send_message(embed=embed)
            return


    #have unauthenticated players, tell user they cannot record a game if all players don't have Venmo verified
    if len(unauthenticatedPlayers) > 0:
            unverifiedUsers = ''
            for p in unauthenticatedPlayers:
                unverifiedUsers += f'{p.mention}, '

            embed = discord.Embed(title= f'❌ Unverified Players', description= f'Users: {unverifiedUsers}have not been verified. Please make sure all players have used the \"**/verify-venmo**\" command.', color=0xf50000)
            await interaction.response.send_message(embed=embed)
            return
    
    #Must have more than one player
    if len(data) <= 1:
        embed = discord.Embed(title= f'❌ Invalid Number of Players', description= f'You must have at least 2 players.', color=0xf50000)
        await interaction.response.send_message(embed=embed)
        return

    #if made it here that means no errors in parameters passed in, defer response while debt settlement algo runs
    await interaction.response.defer()

    #run poker debt settlement algo with error checking
    transactions = []
    try:
        transactions = utilities.poker_debt_settlement_algo(data)

        if transactions == None: #None returned if nonzero sum
            embed = discord.Embed(title= f'❌ Invalid Values', description= f'Please make sure the sum of player buy-ins equals the sum of player winnings.', color=0xf50000)
            await interaction.followup.send(embed=embed)

            print("Error in given arguments: Nonzero total sum")
            return

    except Exception as e:
        embed = discord.Embed(title= f'❌ Unknown Error', description= f'An unknown error has occurred in our algorithm. Please try again.', color=0xf50000)
        await interaction.followup.send(embed=embed)

        print(f"Error in poker debt settlement algorithm: {e}")
        return
    

    #start a session to perform ACID transaction insert of new payment records (if one operation fails, performs rollback of all previous operations in transaction)
    try:
        with db_client.start_session() as session: #explicit session, automatically closes session at the end of the with block
            with session.start_transaction(): #automatically calls commit_transaction if block completes normally, but calls abort_transaction if the with block exits with exception
                for transaction in transactions:
                    await create_outstanding_payments_entry(transaction[0], transaction[1], transaction[2], session)


    except Exception as e:
        print(f"Error in inserting all outstanding payment entries: {e}")
        embed = discord.Embed(title= f'❌ Database Error', description= f'We encountered an error in synchronizing our systems. Please try again.', color=0xf50000)
        await interaction.followup.send(embed=embed)
        return


    embed = discord.Embed(title= f'✅ Your game has been recorded, {interaction.user.name}. Thank you!', color=0x00ff00)
    await interaction.followup.send(embed=embed)


    # await create_outstanding_payments_entry(1234, 5678, 32.5)
    # await create_outstanding_payments_entry(1357, 2468, 17.8)
    # await create_outstanding_payments_entry(1357, 3579, 23.3)
    # await create_outstanding_payments_entry(1357, 3579, 15.5)
    # await create_outstanding_payments_entry(9872, 1627, 12)
    

@bot.tree.command(name="payout", description='Get 1-tap Venmo links for all outstanding payments you have', guild=discord.Object(id=1246667177759608932))
async def payout_cmd(interaction):
    entries = await get_outstanding_payments_entries(interaction.user.id)

    count = 0
    for item in entries:
        venmo_info = item['results']

        if len(venmo_info) < 1:
            print("Recipients venmo account info was not found")
        else:
            #delete the outstanding payments entry from the table
            delete_result = await delete_outstanding_payments_entry(item['debtor'], item['recipient'])

            if delete_result: #successfully deleted
                amount = format(item['amount'], '.2f')
                paymentURL = f"https://venmo.com?url=venmo://paycharge?txn=pay&recipients=@{venmo_info[0]['venmo_usr']}&amount={amount}&note=game"
                embed = discord.Embed(title= f"Payment of **${amount}** to **@{venmo_info[0]['venmo_usr']}**.", description=paymentURL, color=0x00ff00)
            else: #delete failed
                embed = discord.Embed(title= f'❌ Database Error', description= f"We encountered an error in synchronizing our systems for your payment of **${item['amount']}** to **@{venmo_info[0]['venmo_usr']}**. Please use the \'**/payout**\' command again to get the link for this payment.", color=0xf50000)

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