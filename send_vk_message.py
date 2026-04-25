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
    response = requests.get(VK_URL, params=params)
    response.raise_for_status()
    message_data = response.json()
    post_id = message_data['response']['post_id']
    return post_id


def send_vk_photo(image_path, message=""):
    group = str(OWNER_ID).replace('-', '')
    upload_url = requests.get(
        'https://api.vk.com/method/photos.getWallUploadServer',
        params={'access_token': VK_TOKEN, 'v': VK_API_VERSION, 'group_id': group}
    ).json()['response']['upload_url']

    with open(image_path, 'rb') as f:
        upload = requests.post(upload_url, files={'photo': f}).json()

    save = requests.get(
        'https://api.vk.com/method/photos.saveWallPhoto',
        params={'access_token': VK_TOKEN, 'v': VK_API_VERSION, 'group_id': group,
                'photo': upload['photo'], 'server': upload['server'], 'hash': upload['hash']}
    ).json()

    attachment = f"photo{save['response'][0]['owner_id']}_{save['response'][0]['id']}"

    params = {
        'access_token': VK_TOKEN,
        'v': VK_API_VERSION,
        'owner_id': OWNER_ID,
        'attachments': attachment,
        'from_group': 1,
    }
    if message:
        params['message'] = message

    response = requests.post("https://api.vk.com/method/wall.post", params=params)
    return response.json()['response']['post_id']


def delete_vk_message(post_id):
    params = {
        'access_token': VK_TOKEN,
        'v': VK_API_VERSION,
        'owner_id': OWNER_ID,
        'post_id': post_id,

    }

    response = requests.post(VK_URL, params=params)
    response.raise_for_status()
    return f'Пост {post_id} успешно удален'

