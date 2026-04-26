import hashlib
import json
import os
from http.client import responses

import requests
from dotenv import load_dotenv

load_dotenv()

ok_url = 'https://api.ok.ru/fb.do'
APPLICATION_KEY = os.environ['APPLICATION_KEY']
ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
SECRET_KEY = os.environ['SECRET_KEY']
GROUP_ID = os.environ['GROUP_ID']


def generate_sig(params):
    sorted_params = sorted(params.items())
    base = "".join(f'{k}={v}' for k, v in sorted_params)
    base += SECRET_KEY
    return hashlib.md5(base.encode()).hexdigest()


def post_to_ok(text):

    attachment = {'media': [{'type': 'text', 'text': text}]}
    params = {
        'method': 'mediatopic.post',
        'access_token': ACCESS_TOKEN,
        'application_key': APPLICATION_KEY,
        'format': 'json',
        'type': 'GROUP_THEME',
        'gid': GROUP_ID,
        'text': text,
        'attachment': json.dumps(attachment, ensure_ascii=False)

    }

    params['sig'] = generate_sig(params)

    response = requests.post(ok_url, data=params)
    return response.json()


def post_to_photo(image_path, text=''):

<<<<<<< Updated upstream
	params = {
	    'method': 'photosV2.getUploadUrl',
	    'application_key': APPLICATION_KEY,
	    'access_token': ACCESS_TOKEN,
	    'format': 'json',
	    'gid': GROUP_ID,
	}
=======
    params = {
        'method': 'photosV2.getUploadUrl',
        'application_key': APPLICATION_KEY,
        'access_token': ACCESS_TOKEN,
        'format': 'json',
        'gid': GROUP_ID,
    }
>>>>>>> Stashed changes

    params['sig'] = generate_sig(params)
    responses.post(ok_url, data=params)
    data = responses.json()

    if 'upload_url' not in data:
        raise Exception(f"Ошибка: {data}")

<<<<<<< Updated upstream
	with open(image_path, 'rb') as photo_file:
		files = {'file': photo_file}
		upload_response = requests.post(data['upload_url'], files=files)
		upload_data = upload_response.json()
		photo_id = next(iter(upload_data['photos']))
		token = upload_data['photos'][photo_id]['token']
=======
    with open(photo_path, 'rb') as photo_file:
        files = {'file': photo_file}
        upload_response = requests.post(data['upload_url'], files=files)
        upload_data = upload_response.json()
        photo_id = next(iter(upload_data['photos']))
        token = upload_data['photos'][photo_id]['token']
>>>>>>> Stashed changes

    attachment = {'media': [{'type': 'photo', 'list': [
        {'id': token}]}, {'type': 'text', 'text': text}]}
    params = {
        'method': 'mediatopic.post',
        'application_key': APPLICATION_KEY,
        'access_token': ACCESS_TOKEN,
        'format': 'json',
        'type': 'GROUP_THEME',
        'gid': GROUP_ID,
        'text': text,
        'attachment': json.dumps(attachment, ensure_ascii=False),
    }

    params['sig'] = generate_sig(params)
    response = requests.post(ok_url, data=params)
    return response.json()


def delete_post(delete_id):

    params = {
        'method': 'mediatopic.deleteTopic',
        'application_key': APPLICATION_KEY,
        'access_token': ACCESS_TOKEN,
        'format': 'json',
        'gid': GROUP_ID,
        'delete_id': delete_id,
    }

    params['sig'] = generate_sig(params)

    response = requests.post(ok_url, data=params)
    return response.json()
