import json
import os
import asyncio
import datetime
import aiohttp
from aiohttp.client_exceptions import ClientError
from json.decoder import JSONDecodeError


async def add_bot(botname, bot_id):
    file_path = os.path.join('data', 'alivebots.json')
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)      
            data[botname] = bot_id
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        print(f'Added {botname} to the alive bots with ID {bot_id}')
    except Exception as e:
        print(f'Error adding bot: {e}')


async def del_bot(botname, bot_id, alive_file='alivebots.json', dead_file='deadbots.json'):
    dead_file_path = os.path.join('data', dead_file)
    alive_file_path = os.path.join('data', alive_file)   
    try:
        with open(dead_file_path, 'r') as file:
            data = json.load(file)
            data[botname] = bot_id
        with open(dead_file_path, 'w') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        print(f'Added {botname} to the dead bots with ID {bot_id}')
        with open(alive_file_path, 'r') as file:
            data = json.load(file)
            if botname in data:
                del data[botname]
                with open(alive_file_path, 'w') as file:
                    json.dump(data, file, indent=2, ensure_ascii=False)
                print(f'Removed {botname} from the alive bots with ID {bot_id}')
    except Exception as e:
        print(f'Error processing bot removal/addition: {e}')

    
async def add_channel(channel, channel_id):
    file_path = os.path.join('data', 'channels.json')
    with open(file_path) as file:
        old_data = json.load(file)
        if channel not in old_data:
            old_data[channel] = channel_id
            with open(file_path, mode = 'w') as c:
                json.dump(old_data, c, indent=2, ensure_ascii=False)
        print(f"{channel} added to the Bot-Free zone -- ID: {channel_id}")
        await update_total_joined(True)


async def remove_channel(channel_id, channels_file='channels.json'):
    file_path = os.path.join('data', channels_file)
    try:
        with open(file_path, 'r') as c:
            channels_data = json.load(c)
            str_id = str(channel_id)
            channel = next((name for name, id in channels_data.items() if str(id) == str_id), None)
            if channel is None:
                print('No channel found for given ID:', str_id)
                return
            formatted_date = datetime.datetime.now().strftime('%H:%M:%S %m/%d/%Y')
            print('Removing a channel -- ', channel, 'at ', formatted_date)  
            if channel in channels_data:
                del channels_data[channel]
                with open(file_path, 'w') as c:
                    json.dump(channels_data, c, indent=2, ensure_ascii=False)
                    print(channel, '- You have left the bot-free zone', str_id)
            await update_total_joined(False)
    except json.JSONDecodeError:
        print('Error: Could not decode JSON from channels.json')
    except Exception as e:
        print('An unexpected error occurred:', e)


async def update_total_joined(increment=True, filename='totalJoined.txt'):
    file_path = os.path.join('data', filename)
    try:
        with open(file_path, 'r+') as file:
            counter = int(file.read().strip())
            counter += 1 if increment else -1
            file.seek(0)
            file.write(str(counter))
            file.truncate()
        print(f"Total joined updated to: {counter}")
    except FileNotFoundError:
        print(f"{file_path} not found, creating a new file with a counter set to {'1' if increment else '0'}.")
        with open(file_path, 'w') as file:
            file.write('1' if increment else '0')


async def update_counters(name):
    total_bots_path = os.path.join('data', 'totalBots.txt')
    last_ban_path = os.path.join('data', 'lastBan.txt')
    with open(total_bots_path, 'r+') as totalBots:
        counter = int(totalBots.read().strip()) + 1
        totalBots.seek(0)
        totalBots.write(str(counter))
        totalBots.truncate()
    with open(last_ban_path, 'w') as lastBan:
        lastBan.write(name)
    print("totalBots incremented to:", counter)


async def check_if_joined(channel):
    file_path = os.path.join('data', 'channels.json')
    with open(file_path, 'r') as file:
        old_data = json.load(file)
        if channel not in old_data:
            return False
        else:
            return True


async def fetch_bots():
    url = 'https://api.twitchinsights.net/v1/bots/all'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                botlist = await response.json()
                return botlist['bots']
    except aiohttp.ClientResponseError as e:
        print(f'HTTP Error: {e.status} for URL {e.request_info.url}')
    except ClientError as e:
        print(f'Client Error: {e}')
    except JSONDecodeError:
        print('Failed to decode JSON from response')
    except Exception as e:
        print(f'Unexpected error: {e}')
    return None 



async def process_bots(bots):
    new_bots = []
    file_path = os.path.join('data', 'banlist.txt')
    with open(file_path, 'r+') as banlist:
        banned = banlist.read()
        for bot in bots:
            name = bot[0]
            if name not in banned:
                print('new bot found', name)
                new_bots.append(name)
    with open(file_path, 'a') as banlist: 
        for name in new_bots:
            banlist.write(f'{name}\n')
    return new_bots


async def update_last_routine(formatted_date):
    file_path = os.path.join('data', 'lastRoutine.txt')
    with open(file_path, 'w') as lastRoutine:
        lastRoutine.write(formatted_date)


async def check_if_in_limerick(name):
    file_path = os.path.join('data', 'limerick.txt')
    with open(file_path) as limerick:
        lim = limerick.read()
        if name not in lim:
            return False
        else:
            return True


async def add_to_limerick(name):
    file_path = os.path.join('data', 'limerick.txt')
    with open(file_path, 'r+') as limerick:
        lim = limerick.read()
        if name not in lim:
            print('adding user', name, 'to the limericks')
            limerick.write(f'{name}\n')


async def del_from_limerick(name):
    file_path = os.path.join('data', 'limerick.txt')
    with open(file_path) as limerick:
        lines = limerick.readlines()
        lines = [line for line in lines if name not in line]
    with open(file_path, 'w') as limerick:
        limerick.writelines(lines)     
    print(f'Removed user {name} from the limericks')
