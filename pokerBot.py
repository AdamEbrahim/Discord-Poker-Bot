import os
import discord
import asyncio
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

#default intents with members enabled
intents = discord.Intents.default()
intents.members = True #now needs privileged intents enabled for members
intents.message_content = True

#create bot object to interact with discord API 
bot = commands.Bot(command_prefix='/', intents=intents)

#--EVENTS--#
@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


async def get_venmo_user(member):
    embed = discord.Embed(title=f'Hello, {member.name}. Please send your Venmo username (the name after the \"@\").',
                                 description='Please make sure it is accurate so that you can receive your Poker winnings. This message will time out in 2 minutes.',
                                 color=0x800080)
    await member.dm_channel.send(embed=embed)
    
    def check(msg):
        return msg.channel == member.dm_channel and msg.author == member
    
    def check2(reaction, user):
        return user == member and (str(reaction.emoji) == '❌' or str(reaction.emoji) == '✅')
    
    verified = False
    while not verified:
        try:
            username = await bot.wait_for('message', timeout=30.0, check=check) #2 minute time out
        except asyncio.TimeoutError:
            embed = discord.Embed(title='TIMEOUT OCCURRED 👎', description='Please use the \"verify-venmo\" command to try again.', color=0xf50000)
            await member.dm_channel.send(embed=embed)
            return

        embed = discord.Embed(title='CONFIRMATION', description=f'Please confirm that your venmo username is \"@{username.content}\". This will time out in 2 minutes.', color=0x800080)
        confirmation_msg = await member.dm_channel.send(embed=embed)
        await confirmation_msg.add_reaction('❌')
        await confirmation_msg.add_reaction('✅')

        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=120.0, check=check2)
        except asyncio.TimeoutError:
            embed = discord.Embed(title='TIMEOUT OCCURRED 👎', description='Please use the \"verify-venmo\" command to try again.', color=0xf50000)
            await member.dm_channel.send(embed=embed)
            return
        else:
            if str(reaction.emoji) == '❌':
                embed = discord.Embed(title='Please resend your Venmo username (the name after the \"@\").',
                                 description='This message will time out in 2 minutes.',
                                 color=0xf50000)
                await member.dm_channel.send(embed=embed)
                
            elif str(reaction.emoji) == '✅':
                await confirmation_msg.delete()
                verified = True

            else:
                embed = discord.Embed(title='UNKNOWN ERROR 👎', description='Please use the \"verify-venmo\" command to try again.', color=0xf50000)
                await member.dm_channel.send(embed=embed)
                return

    #Now they must be verified
    embed = discord.Embed(title= "Venmo account confirmed. Thank you!", color=0x00ff00)
    await member.dm_channel.send(embed=embed)


@bot.event
async def on_member_join(member):
    if member.dm_channel == None:
        await member.create_dm()

    await get_venmo_user(member)

    
        

@bot.command(name='verify-venmo', help='Use this command to connect your Venmo username to your account to receive future Poker earnings.')
async def verify_venmo_cmd(ctx):
    if ctx.author.dm_channel == None:
        await ctx.author.create_dm()

    if ctx.channel != ctx.author.dm_channel:
        await ctx.channel.send(f'{ctx.author.mention} Please check dms!')

    await get_venmo_user(ctx.author)
    


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