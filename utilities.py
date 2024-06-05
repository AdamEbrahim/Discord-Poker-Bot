import discord
import asyncio

async def can_dm_user(member: discord.User):
    if member.dm_channel == None:
        await member.create_dm()

    try:
        await member.dm_channel.send() #send empty message to see if forbidden (cant dm user) or just throws an error because of empty content
    except discord.Forbidden:
        return False
    except discord.HTTPException:
        return True