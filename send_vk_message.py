import requests
from dotenv import load_dotenv
import os


load_dotenv()

VK_URL = "https://api.vk.com/method/wall.post"
VK_API_VERSION = 5.199
VK_TOKEN = os.environ['VK_TOKEN']
OWNER_ID = os.environ['OWNER_ID']


def send_vk_message(message, from_group=1):
    params = {
        'access_token': VK_TOKEN,
        'v': VK_API_VERSION,
        'owner_id': OWNER_ID,
        'message': message,
        'from_group': from_group,
    }

    response = requests.get(vk_url, params=params)
    response.raise_for_status()
    message_data = response.json()
    post_id = message_data['response']['post_id']
    return post_id


def send_vk_photo(attachments, from_group=1):
    params = {
        'access_token': VK_TOKEN,
        'v': VK_API_VERSION,
        'owner_id': OWNER_ID,
        'attachments': '2026-04-22_17-49-28.png'
    }
    response = requests.get(vk_url, params=params)
    response.raise_for_status()

    photo_data = response.json()
    post_id = photo_data[0]['id']
    return post_id


def delete_vk_message(post_id):
    params = {
        'access_token': VK_TOKEN,
        'v': VK_API_VERSION,
        'owner_id': OWNER_ID,
        'post_id': post_id,

    }

    response = requests.get(vk_url, params=params)
    response.raise_for_status()
    return f'Пост {post_id} успешно удален'


send_vk_message('Привет')
