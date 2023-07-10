import requests
import json
import time
import json
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
import os

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore


class Sender:

    def __init__(self, 
                 params):
        
        self.params = params
        self.sender_initializer()

    def sender_initializer(self):

        with open(self.params, "r") as json_file:
            params = json.load(json_file)

        self.channelid=params['channelid']
        self.authorization=params['authorization']
        self.application_id = params['application_id']
        self.guild_id = params['guild_id']
        self.session_id = params['session_id']
        self.version = params['version']
        self.id = params['id']
        self.flags = params['flags']
        
        
    def send(self, prompt):
        header = {
            'authorization': self.authorization
        }

        payload = {'type': 2, 
        'application_id': self.application_id,
        'guild_id': self.guild_id,
        'channel_id': self.channelid,
        'session_id': self.session_id,
        'data': {
            'version': self.version,
            'id': self.id,
            'name': 'imagine',
            'type': 1,
            'options': [{'type': 3, 'name': 'prompt', 'value': str(prompt) + ' ' + self.flags}],
            'attachments': []}
            }

        print('prompt [{}] is sending...'.format(prompt))
        
        r = requests.post('https://discord.com/api/v9/interactions', json = payload , headers = header)
        return r

        # while r.status_code != 204:
        #     r = requests.post('https://discord.com/api/v9/interactions', json = payload , headers = header)
        print('prompt [{}] successfully sent!'.format(prompt))


app = Flask(__name__)
CORS(app)
cors = CORS(app, resource={
    r"/*":{
        "origins":"*"
    }
})

@app.route('/imagine', methods=['POST'])
@cross_origin()
def imagine():
    try:
        params = os.path.abspath(os.getcwd()) + '/sender_params.json'
        prompt = json.loads(request.data)

        body_prompt = prompt['prompt']
        story_ref = prompt['storyReference']
        image_url = prompt['image']

        uid = story_ref[:-15]

        body_prompt += ' ' + uid

        doc_ref = db.collection('stories').document(story_ref)
        doc_ref.update({"proc_id": body_prompt.replace(" ", "_")})

        sender = Sender(params)
        response = sender.send(image_url + ' ' + body_prompt)

        encoding = 'utf-8'
        json_str = json.dumps({})

        return json_str
    except Exception as e: print(e)


# Initialize the Firebase Admin SDK
cred = credentials.Certificate('config/serviceAccountKey.json')
firebase_admin.initialize_app(cred)

# Create a Firestore client
db = firestore.client()

# cert = os.path.abspath(os.getcwd()) + '/server.crt'
# key = os.path.abspath(os.getcwd()) + '/server.key'
# app.run( host='0.0.0.0', port=5000, ssl_context=(cert, key))
app.run( host='0.0.0.0', port=5000)