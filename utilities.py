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
    Debt Settlement Algorithm, which reduces to the Optimal Zero-Sum Set Packing problem 
    (Finding the maximum number of zero sum sets you can partition X = [debt1, debt2, ...] into is 
    equivalent to finding the minimum number of transactions)
    data is a list of lists, where each list has the form [player_id, player_buy_in, player_winnings]

    The algorithm is a Greedy algorithm that uses a max_heap and min_heap to reduce
    the time complexity to O(nlogn)

    OR

    The algorithm is a brute force approach 

    """
    
    #get amount owed to each player (negative if they owe)
    data = [[data[i][0], round(data[i][2] - data[i][1], 2)] for i in range(len(data))]

    #if total amount owed among everyone does not equal 0, there is an error in provided values
    if round(sum(row[1] for row in data), 2) != 0:
        return None
    
    print(data)


from itertools import combinations
from functools import reduce
from collections import defaultdict

def find_zero_sum_subsets(debts, k):
    """Find all subsets of size <= k whose sum is zero."""
    zero_sum_subsets = []
    for size in range(2, k + 1):
        for subset in combinations(enumerate(debts), size):
            indices, subset_debts = zip(*subset)
            if sum(subset_debts) == 0:
                zero_sum_subsets.append(indices)
    return zero_sum_subsets

def k_set_packing_approximation(debts, k):
    """Implement k-set packing approximation."""
    zero_sum_subsets = find_zero_sum_subsets(debts, k)
    
    # Create a graph where nodes are people and edges are zero sum subsets
    graph = defaultdict(list)
    for subset in zero_sum_subsets:
        for i in subset:
            graph[i].append(subset)
    
    # Greedily select disjoint subsets
    selected_subsets = []
    used_indices = set()
    for subset in zero_sum_subsets:
        if not any(index in used_indices for index in subset):
            selected_subsets.append(subset)
            used_indices.update(subset)
    
    # Settle debts using selected subsets
    transactions = []
    for subset in selected_subsets:
        if len(subset) > 1:
            transactions.append(subset)
    
    return transactions, used_indices

def settle_debts(debts, max_k=5):
    """Settle debts using an adaptive k-set packing approximation."""
    n = len(debts)
    for k in range(2, max_k + 1):
        transactions, used_indices = k_set_packing_approximation(debts, k)
        if len(used_indices) == n:
            return transactions, k
    
    # If max_k is reached and not all debts are settled, return the best found solution
    return transactions, max_k

# Example usage
debts = [10, 49, 50, 65, -75, -99, 27, -7, -10, -10, 10, 39, 50, 65, -75, -89, 31, -7, -14, -10]
#[-75, 65, 27, 65, -75, -7] -> [65, 65, 27, -7, -75, -75]
#THEN DO GREEDY TO DETERMINE WHO WITHIN A ZERO-SUM-SET PAYS WHO (guaranteed to be minimal)
max_k = 10
transactions, chosen_k = settle_debts(debts, max_k)
print("Transactions to settle debts:", transactions)
print("Chosen k:", chosen_k)