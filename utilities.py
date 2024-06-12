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
    


def poker_debt_settlement_algo(data: list[list]):
    """
    Algorithm to implement poker debt settlement. 
    data is a list of lists, where each list has the form [player_id, player_buy_in, player_winnings]
    """
    
    #get amount owed to each player (negative if they owe)
    data = [[data[i][0], round(data[i][2] - data[i][1], 2)] for i in range(len(data))]

    #if total amount owed among everyone does not equal 0, there is an error in provided values
    if round(sum(row[1] for row in data), 2) != 0:
        return None
    
    print(data)