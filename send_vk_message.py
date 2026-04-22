import requests
from dotenv import load_dotenv
import os

load_dotenv()

VK_API_VERSION = 5.199

def send_vk_message(message, from_group=1):
    vk_url = "https://api.vk.com/method/wall.post"
    vk_token = os.environ['VK_TOKEN']
    owner_id = os.environ['OWNER_ID']

    params = {
        'access_token': vk_token,
        'v': VK_API_VERSION,
        'owner_id': owner_id,
        'message': message,
        'from_group': from_group,
    }

    response = requests.get(vk_url, params=params)
    response.raise_for_status()

    message_data = response.json()
    post_id = message_data['response']['post_id']
    return post_id


def delete_vk_message(post_id):
    vk_url = "https://api.vk.com/method/wall.delete"
    vk_token = os.environ['VK_TOKEN']
    owner_id = os.environ['OWNER_ID']

    params = {
        'access_token': vk_token,
        'v': VK_API_VERSION,
        'owner_id': owner_id,
        'post_id': post_id,

    }

    response = requests.get(vk_url, params=params)
    response.raise_for_status()
    return f'Пост {post_id} успешно удален'
