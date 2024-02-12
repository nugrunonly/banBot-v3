from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, EventData, ChatMessage, ChatCommand
from twitchAPI.helper import first
from utils import *
from gpt import create_prompt
import asyncio
import os
import aiohttp
import json
import datetime
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join('config', '.env'))

class BOT:
    def __init__(self, app_id, app_secret, user_scope, target_channel):
        self.app_id = app_id
        self.app_secret = app_secret
        self.user_scope = user_scope
        self.target_channel = target_channel
        self.twitch = None
        self.chat = None
        self.bot_id = os.environ['BOT_ID']
        self.bot_name = os.environ['BOT_NAME']
        

    async def on_ready(self, ready_event: EventData):
        print('Bot is ready for work')
        await ready_event.chat.join_room(self.target_channel)
        await self.loop_stuff()


    async def on_message(self, msg: ChatMessage):
        print(f'in {msg.room.name}, {msg.user.name} said: {msg.text}')


    async def get_user_id(self, username):
        try:
            user = await first(self.twitch.get_users(logins=[username]))
            return user.id
        except Exception as e:
            print(f"Error: {e}")
            return None
        

    async def build_banlist(self):
        url = 'https://api.twitchinsights.net/v1/bots/all'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    botlist = await response.json()
                    bots = botlist['bots']
                    for name in range(len(bots)):
                        user_id = await self.get_user_id(bots[name][0])
                        if user_id is None:
                            await self.del_bot(bots[name][0], user_id)
                        else:
                            await self.add_bot(bots[name][0], user_id)
                        await asyncio.sleep(0.1)
                else:
                    print(f"Failed to fetch data. Status code: {response.status}")


    async def join(self, input):
        if isinstance(input, ChatCommand):
            name = input.user.name
        elif isinstance(input, str):
            name = input
        else:
            raise ValueError("Unsupported input type for join operation.")
        user_id = await self.get_user_id(name)
        has_joined = await check_if_joined(name)
        if not has_joined:
            await add_channel(name, user_id)
            finished = await self.mass_ban(name, user_id)
            if finished:
                if isinstance(input, ChatCommand):
                    await self.chat.send_message(self.bot_name, f'{name}, you are now protected.')
                else:
                    print(f'{name} forcefully added to the join list and is now protected.')
        else:
            if isinstance(input, ChatCommand):
                await self.chat.send_message(self.bot_name, f'{name}, You are already protected.')
            else:
                print(f'Unable to add {name} to the join list because they are already protected.')


    async def leave(self, input):
        if isinstance(input, ChatCommand):
            name = input.user.name
        elif isinstance(input, str):
            name = input
        else:
            raise ValueError("Unsupported input type for join operation.")
        user_id = await self.get_user_id(name)
        has_joined = await check_if_joined(name)
        if has_joined:
            await remove_channel(user_id)
            await self.twitch.remove_channel_moderator(user_id, self.bot_id)
            await del_from_limerick(name)
            if isinstance(input, ChatCommand):
                await self.chat.send_message(self.bot_name, f'You have left the bot-free zone, {name}, New bots will no longer be banned on your channel.')   
            else:
                print(f'{name}')   
        else:
            if isinstance(input, ChatCommand):
                await self.chat.send_message(self.bot_name, f'{name}, you were not on my protected list.')
            else:
                print(f'{name} was not on our protected list, unable to remove.')


    async def leave_and_unban(self, cmd: ChatCommand):
        user_id = await self.get_user_id(cmd.user.name)
        has_joined = await check_if_joined(cmd.user.name)
        if has_joined:
            await self.mass_unban(cmd.user.name, user_id)
            await remove_channel(user_id)
            await del_from_limerick(cmd.user.name)
            try:
                await self.twitch.remove_channel_moderator(user_id, self.bot_id)
            except Exception as e:
                print(f'Error removing mod (probably already dont have it) - {e}')
            await self.chat.send_message(self.bot_name, f'{cmd.user.name} -- You have left the bot-free zone and I have unbanned all bots on your channel.')
        else:
            await self.chat.send_message(self.bot_name, f'{cmd.user.name}, you are not currently my protected list, unable to mass-unban.')
    

    async def ban_bot(self, username, channel_id, channel):
        ban_successful = await self.ban(username, channel_id, channel)
        if ban_successful == channel:
            await self.chat.send_message(self.bot_name, f'@{username}, {self.bot_name} needs to be a moderator on your channel to work! Stopping services on your channel.')
    

    async def ban(self, username, channel_id, channel, reason='Bot'):
        user_id = await self.get_user_id(username)
        if user_id is None:
            print(f'Error: Could not find user {username}')
            await del_bot(username, user_id)
            return None
        try:
            await self.twitch.ban_user(channel_id, self.bot_id, user_id, reason)
            print(f'Banned user {username} from channel ({channel})')
        except KeyError as e:
            if e.args and e.args[0] == 'data':
                print(f'Error: The "data" key is missing in the response while banning user {username} in channel {channel}.')
                await remove_channel(channel_id)
                print('Bot does not have moderator permissions in channel so we left:', channel)
                return channel
            else:
                print(f'KeyError: {e}. User {username} not banned in channel {channel}, likely already banned or does not exist.')
                return None
        except Exception as e:
            print(f'An unexpected error occurred while banning user {username} in channel {channel_id}: {e}')
            return None
        
    
    async def unban(self, username, channel_id, channel):
        user_id = await self.get_user_id(username)
        if user_id is None:
            print(f'{username} got perma-banned. Added to deadbots.')
            await del_bot(username, user_id)
            return None  
        try:
            await self.twitch.unban_user(channel_id, self.bot_id, user_id)
            print(f'Unbanned user {username} from channel ({channel})')
            return None
        except KeyError as e:
            if e.args and e.args[0] == 'data':
                print(f'Error: The "data" key is missing in the response while banning user {username} in channel {channel}.')
                await remove_channel(channel_id)
                print(f'Error: Lacking permissions to unban {username} in channel {channel_id} so we left.')
                return channel
            else:
                print(f'KeyError: {e}.')
                return None
        except Exception as e:
            print(f"An unexpected error occurred while unbanning {username} in channel {channel_id}: {e}")
            return None  


    async def mass_ban(self, channel, channel_id):  
        await self.chat.send_message(self.bot_name, f'Starting mass exodus of bots on {channel}\'s channel. This can take around ~1hr, please be patient...')
        finished = await self.massban_from_channel(channel, channel_id)
        if finished == channel:
            await self.chat.send_message(self.bot_name, f'@{channel}, Please add {self.bot_name} as a moderator and try again (sometimes it takes a minute or two to register the new mod).')
        else:
            await self.chat.send_message(self.bot_name, f'Finished banning all bots on {channel}\'s channel.')
            await update_total_joined(True)
    

    async def massban_from_channel(self, channel, channel_id):
        file_path = os.path.join('data', 'alivebots.json')
        with open(file_path, 'r') as file:
            active_bots = json.load(file)
            for bot_name, bot_id in active_bots.items():
                try:
                    result = await self.ban(bot_name, channel_id, channel)
                    if result == channel:
                        return channel
                    print(f"Mass exodus on {channel}'s channel -- {bot_name}, {bot_id}")
                    await asyncio.sleep(0.4)
                except Exception as e:
                    print(f'Error: {e}')
        return None



    async def mass_unban(self, channel, channel_id):
        await self.chat.send_message(self.bot_name, f'Starting mass unbanning of bots on {channel}\'s channel. This can take around ~1hr, please be patient and do not unmod {self.bot_name} until it is over...')
        finished = await self.mass_unban_from_channel(channel, channel_id)
        await asyncio.sleep(1)
        if finished == channel:
            await self.chat.send_message(f'@{channel}, Please add {self.bot_name} as a moderator and try again.')
        if finished:
            await self.chat.send_message(self.bot_name, f'Finished unbanning all bots on {channel}\'s channel.')
            await update_total_joined(False)

    
    async def mass_unban_from_channel(self, channel, channel_id):
        file_path = os.path.join('data', 'alivebots.json')
        with open(file_path, 'r') as file:
            active_bots = json.load(file)
            for bot_name, bot_id in active_bots.items():
                try:
                    await self.unban(bot_name, channel_id, channel)
                    print(f"Mass unbanning on {channel}'s channel -- {bot_name}, {bot_id}")
                    await asyncio.sleep(0.4)
                except Exception as e:
                    print(f'No mod privileges on channel {channel}, stopping the mass-unban. Error: {e}')
                    return channel
        return None


    async def ban_routine(self):
        bots = await fetch_bots()
        formatted_date = datetime.datetime.now().strftime('%H:%M:%S %m/%d/%Y')
        new_bots = await process_bots(bots)
        if new_bots:
            await self.handle_new_bots(new_bots)
        await update_last_routine(formatted_date)
        print('Super_Ban list Updated at', formatted_date)


    async def handle_new_bots(self, result):
        for name in result:
            try:
                user_id = await self.get_user_id(name)
                await add_bot(name, user_id)
                await self.ban_in_channels(name, user_id)
                await update_counters(name)
                await self.tell_story(name)
            except Exception as e:
                print(f'Error handling the bot {name}: {e}')


    async def ban_in_channels(self, name, user_id):
        file_path = os.path.join('data', 'channels.json')
        with open(file_path, 'r') as channels:
            channel_data = json.load(channels)
            for channel in channel_data:
                await self.ban_bot(name, channel_data[channel], channel)
                await asyncio.sleep(0.4)

    async def alert(self, cmd: ChatCommand):
        if await check_if_joined(cmd.user.name):
            in_limerick = await check_if_in_limerick(cmd.user.name)
            if not in_limerick:
                await add_to_limerick(cmd.user.name)
                await self.chat.send_message(self.bot_name, f'{cmd.user.name} - You have been added to the silly limericks alerts')
            else:
                await self.chat.send_message(self.bot_name, f'{cmd.user.name} - You are already added to the limerick alerts')
        else:
            await self.chat.send_message(self.bot_name, f'{cmd.user.name}, you need to join first before managing limerick alerts.')

    async def noalert(self, cmd: ChatCommand):
        if await check_if_joined(cmd.user.name):
            in_limerick = await check_if_in_limerick(cmd.user.name)
            if in_limerick:
                await del_from_limerick(cmd.user.name)
                await self.chat.send_message(self.bot_name, f'{cmd.user.name} - You have been removed from the silly limericks alerts')
            else:
                await self.chat.send_message(self.bot_name, f'{cmd.user.name} - You were not receiving alerts.')
        else:
            await self.chat.send_message(self.bot_name, f'{cmd.user.name}, you need to join first before managing limerick alerts.')



    async def tell_story(self, name):
        try:
            completion = create_prompt(name)
            print(f'sad story about {name}', completion)
            file_path = os.path.join('data', 'limerick.txt')
            with open(file_path, 'r') as limericks:
                for line in limericks:
                    chan = line.strip()
                    await self.chat.send_message(chan, completion.choices[0].message.content)
                    await asyncio.sleep(0.4)
        except Exception as e:
            print('found error', e)


    async def run_periodically(self, coro, interval_seconds):
        while True:
            await asyncio.sleep(interval_seconds)
            await coro()


    async def loop_stuff(self):
        interval_seconds = 900
        coro = self.ban_routine
        await coro()
        asyncio.create_task(self.run_periodically(coro, interval_seconds))
        

    async def run(self):
        self.twitch = await Twitch(self.app_id, self.app_secret)
        auth = UserAuthenticator(self.twitch, self.user_scope)
        token, refresh_token = await auth.authenticate()
        await self.twitch.set_user_authentication(token, self.user_scope, refresh_token)

        self.chat = await Chat(self.twitch)
        self.chat.register_event(ChatEvent.READY, self.on_ready)
        self.chat.register_event(ChatEvent.MESSAGE, self.on_message)
        self.chat.register_command('join', self.join)
        self.chat.register_command('leave', self.leave)
        self.chat.register_command('ilovebots', self.leave_and_unban)
        self.chat.register_command('alert', self.alert)
        self.chat.register_command('noalert', self.noalert)
        self.chat.start()

        try:
            input('press ENTER to stop\n')
        finally:
            self.chat.stop()
            await self.twitch.close()


if __name__ == '__main__':
    APP_ID = os.environ['APP_ID']
    APP_SECRET = os.environ['APP_SECRET']
    USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CHAT_EDIT, AuthScope.MODERATOR_MANAGE_BANNED_USERS, AuthScope.CHANNEL_MANAGE_MODERATORS]
    TARGET_CHANNEL = os.environ['BOT_NAME']

    bot = BOT(APP_ID, APP_SECRET, USER_SCOPE, TARGET_CHANNEL)
    asyncio.run(bot.run())
