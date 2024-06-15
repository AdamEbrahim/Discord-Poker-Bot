import discord
import asyncio
from itertools import combinations
from functools import reduce
from collections import defaultdict

async def can_dm_user(member: discord.User):
    if member.dm_channel == None:
        await member.create_dm()

    try:
        await member.dm_channel.send() #send empty message to see if forbidden (cant dm user) or just throws an error because of empty content
    except discord.Forbidden:
        return False
    except discord.HTTPException:
        return True
    

def find_zero_sum_subsets(debts, k, epsilon=1e-9):
    """Find all subsets of size <= k whose sum is close to zero."""
    zero_sum_subsets = []
    for size in range(2, k + 1):
        for subset in combinations(enumerate(debts), size):
            indices, subset_debts = zip(*subset)
            if abs(sum(subset_debts)) < epsilon:
                zero_sum_subsets.append(indices)
    return zero_sum_subsets

def k_set_packing_approximation(debts, k, epsilon=1e-9):
    """Implement k-set packing approximation."""
    zero_sum_subsets = find_zero_sum_subsets(debts, k, epsilon)
    
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

def get_minimum_transaction_sets(debts, max_k=5, epsilon=1e-9):
    """
    Get max disjoint zero sum sets using an adaptive k-set packing approximation.
    The return value will be all sets s such that in s.size() - 1 transactions the 
    set's debt can be settled. Across all sets this is the minimum number of
    transactions needed to settle all debts. O(n^k) runtime.
    """
    n = len(debts)
    for k in range(2, max_k + 1):
        transactions, used_indices = k_set_packing_approximation(debts, k, epsilon)
        if len(used_indices) == n:
            return transactions, k
    
    # If max_k is reached and not all debts are settled, return the best found solution
    return transactions, max_k

def greedy(debts: list[list[float,int]]):
    """
    Greedy algo
    """

    #sort in ascending order (max creditor, .., max debtor)
    debts.sort(key=lambda x: x[1])

    currCreditorIdx = 0
    currDebtorIdx = len(debts) - 1

    transactions = [0 for i in range(len(debts) - 1)] # n-1 transactions to settle all debts
    iterator = 0

    while currCreditorIdx < currDebtorIdx:

        transactions[iterator] = [debts[currDebtorIdx][0], debts[currCreditorIdx][0], 0]

        if abs(debts[currCreditorIdx][1]) < debts[currDebtorIdx][1]:

            transactions[iterator][2] = abs(debts[currCreditorIdx][1])
            debts[currDebtorIdx][1] = round(debts[currDebtorIdx][1] + debts[currCreditorIdx][1], 2)
            currCreditorIdx = currCreditorIdx + 1

        elif abs(debts[currCreditorIdx][1]) > debts[currDebtorIdx][1]:

            transactions[iterator][2] = debts[currDebtorIdx][1]
            debts[currCreditorIdx][1] = round(debts[currCreditorIdx][1] + debts[currDebtorIdx][1], 2)
            currDebtorIdx = currDebtorIdx - 1
            
        else:

            transactions[iterator][2] = abs(debts[currCreditorIdx][1])
            currCreditorIdx = currCreditorIdx + 1
            currDebtorIdx = currDebtorIdx - 1

        iterator = iterator + 1
 
    return transactions


def poker_debt_settlement_algo(data):
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
    
    #get player debts (positive if they are in debt and owe, negative if have credit and are owed)
    data = [[data[i][0], round(data[i][1] - data[i][2], 2)] for i in range(len(data))]
    debts = [row[1] for row in data]

    #if total amount owed among everyone does not equal 0, there is an error in provided values
    if round(sum(debts), 2) != 0:
        return None


    # debts = [10, 49, 50, 65, -75, -99, 27, -7, -10, -10, 10, 39, 50, 65, -75, -89, 31, -7, -14, -10]
    # debts = [5, 5, 5, 5, 5]
    # debts = [6.45, 4.78, 3.92, 5.61, 4.24]
    # debts = [-1.47, .22, 1.12, -.61, .76, -1.40, .19, 1.16, -.75, .78]

    max_k = 10
    transactions, chosen_k = get_minimum_transaction_sets(debts, max_k) #returns indices of the groups
    print("Transactions to settle debts:", transactions)
    print("Chosen k:", chosen_k)

    final_transactions = [0 for i in range(len(data) - len(transactions))] #total number of transactions across all zero sum sets is n - k where k is number of zero sum sets
    iterator = 0

    #THEN DO GREEDY TO DETERMINE WHO WITHIN A ZERO-SUM-SET PAYS WHO (guaranteed to be minimal)
    for zero_sum_set in transactions:
        groupedData = [0 for i in range(len(zero_sum_set))]

        for i in range(len(zero_sum_set)):
            groupedData[i] = data[zero_sum_set[i]]

        res = greedy(groupedData)
        for transaction in res:
            final_transactions[iterator] = transaction
            iterator = iterator + 1

    return final_transactions


#print(poker_debt_settlement_algo([[1,2.5,0],[3,4.35,0],[4,-6.85,0]]))
#print(poker_debt_settlement_algo([[1,2.5,0],[3,4.35,0],[4,-6.85,0],[7,4,4]])) #deal with 0's
print(poker_debt_settlement_algo([[1,2.5,0],[4,-2.8,0],[4,2.8,0],[3,4.35,0],[4,-6.85,0]]))