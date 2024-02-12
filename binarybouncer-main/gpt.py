import openai
import os
from retrying import retry
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join('config', '.env'))

openai.api_key = os.environ['API_KEY']


@retry(stop_max_attempt_number=3, wait_fixed=2000)
def create_prompt(prompt):
    print('attempting to create a prompt')
    return openai.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": f"In less than 60 words, please write a limerick about a bot named {prompt} that got banned from Twitch."}], temperature=1.2)