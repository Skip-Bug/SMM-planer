import requests
from dotenv import load_dotenv
import os

load_dotenv()


def send_vk_message():
    vk_url = "https://api.vk.com/method/wall.post"
    vk_token = os.environ['VK_TOKEN']

    params = {
        'access_token': vk_token,
        'v': '5.199',
        'owner_id': '-237933972',
        'message': 'Привет от Кирюши',
        'from_group': 1

    }

    response = requests.get(vk_url, params=params)
    response.raise_for_status()

    if response.status_code == 200:
        print('Успешно')
    else:
        print('Ошибка при отправке сообщения')

send_vk_message()