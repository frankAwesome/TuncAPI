import requests
import json
import time
import pandas as pd
import os
from datetime import datetime
from PIL import Image

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from firebase_admin import storage

import re


class Receiver:

    def __init__(self,
                 params,
                 local_path):

        self.params = params
        self.local_path = local_path

        self.sender_initializer()

        self.df = pd.DataFrame(columns=['prompt', 'url', 'filename', 'is_downloaded'])

    def sender_initializer(self):

        with open(self.params, "r") as json_file:
            params = json.load(json_file)

        self.channelid = params['channelid']
        # self.authorization = params['authorization']
        self.authorization = os.getenv('AUTHTOKEN','NjMwNzYxMzIwMjA3MDg5NzA1.GoqmY4.vtUQs3u22uSV1hgGCasMzRsXXEqzCrtoT2w5MA')
        self.headers = {'authorization': self.authorization}

    def retrieve_messages(self):
        r = requests.get(
            f'https://discord.com/api/v10/channels/{self.channelid}/messages?limit={100}', headers=self.headers)
        print(r)
        jsonn = json.loads(r.text)
        return jsonn

    def collecting_results(self):
        message_list = self.retrieve_messages()
        self.awaiting_list = pd.DataFrame(columns=['prompt', 'status'])
        for message in message_list:

            if (message['author']['username'] == 'Midjourney Bot') and ('**' in message['content']):

                if len(message['attachments']) > 0:

                    if (message['attachments'][0]['filename'][-4:] == '.png') or (
                            '(Open on website for full quality)' in message['content']):
                        id = message['id']
                        prompt = message['content'].split('**')[1].split(' --')[0]
                        url = message['attachments'][0]['url']
                        filename = message['attachments'][0]['filename']
                        if id not in self.df.index:
                            self.df.loc[id] = [prompt, url, filename, 0]

                    else:
                        id = message['id']
                        prompt = message['content'].split('**')[1].split(' --')[0]
                        if ('(fast)' in message['content']) or ('(relaxed)' in message['content']):
                            try:
                                status = re.findall("(\w*%)", message['content'])[0]
                            except:
                                status = 'unknown status'
                        self.awaiting_list.loc[id] = [prompt, status]

                else:
                    id = message['id']
                    prompt = message['content'].split('**')[1].split(' --')[0]
                    if '(Waiting to start)' in message['content']:
                        status = 'Waiting to start'
                    self.awaiting_list.loc[id] = [prompt, status]

    def outputer(self):
        if len(self.awaiting_list) > 0:
            print(datetime.now().strftime("%H:%M:%S"))
            print('prompts in progress:')
            print(self.awaiting_list)
            print('=========================================')

        waiting_for_download = [self.df.loc[i].prompt for i in self.df.index if self.df.loc[i].is_downloaded == 0]
        if len(waiting_for_download) > 0:
            print(datetime.now().strftime("%H:%M:%S"))
            print('waiting for download prompts: ', waiting_for_download)
            print('=========================================')

    def downloading_results(self, db, bucket):
        processed_prompts = []
        for i in self.df.index:
            if self.df.loc[i].is_downloaded == 0:

                file_path = 'processed.txt'
                image_url = self.df.loc[i].filename
                contains_image_url = check_image_url(file_path, image_url)
                if contains_image_url:
                    print("The file contains the provided image URL.")
                else:
                    response = requests.get(self.df.loc[i].url)
                    with open(os.path.join(self.local_path, self.df.loc[i].filename), "wb") as req:
                        req.write(response.content)

                        # Example usage
                        image_path = self.df.loc[i].filename  # Replace with your image path
                        base_name = self.df.loc[i].filename  # Replace with your desired base name
                        cut_square_image(image_path, base_name)

                        filename = image_path
                        extracted_string = filename[9:14]

                        print(extracted_string)

                        story_doc = get_document_by_field('stories', 'proc_id', extracted_string, db)

                        desired_value = extracted_string
                        directory = 'crops/'
                        uploaded_urls = []

                        for filename in os.listdir(directory):
                            if desired_value in filename:
                                file_path = os.path.join(directory, filename)
                                blob = bucket.blob(filename)
                                blob.upload_from_filename(file_path)
                                blob.make_public()
                                url = blob.public_url
                                uploaded_urls.append(url)

                        inc = 8

                        for file in uploaded_urls:
                            referenced_document_ref = db.collection('stories').document(story_doc.id)
                            document_data = {
                                'image_url': file,
                                'story': referenced_document_ref,
                                'order': inc
                            }
                            inc += 1

                            collection_ref = db.collection('slide')
                            new_document_ref = collection_ref.document()
                            new_document_ref.set(document_data)

                        referenced_document_ref.update({"in_review": False})

                self.df.loc[i, 'is_downloaded'] = 1
                processed_prompts.append(self.df.loc[i].prompt)
        if len(processed_prompts) > 0:
            print(datetime.now().strftime("%H:%M:%S"))
            print('processed prompts: ', processed_prompts)
            print('=========================================')

    def main(self):
        # Initialize the Firebase Admin SDK
        cred = credentials.Certificate('config/serviceAccountKey.json')

        firebase_admin.initialize_app(cred, {
            'storageBucket': 'storysocial-23aa1.appspot.com'
        })

        # Create a Firestore client
        db = firestore.client()
        bucket = storage.bucket()

        while True:
            try:
                self.collecting_results()
                self.outputer()
                self.downloading_results(db=db, bucket=bucket)
                time.sleep(30)
            except Exception as e:
                print(e)



def check_image_url(file_path, image_url):
    found = False
    with open(file_path, 'r+') as file:
        lines = file.readlines()
        for line in lines:
            if image_url in line:
                found = True
                break

        if not found:
            file.write(image_url + '\n')

    return found


def cut_square_image(image_path, base_name):
    # Open the image

    img = Image.open(os.path.abspath(os.getcwd()) + '/download/' + image_path)

    # Ensure the image is square
    width, height = img.size
    min_dim = min(width, height)
    img = img.crop((0, 0, min_dim, min_dim))

    # Calculate the dimensions for each sub-image
    sub_width = min_dim // 2
    sub_height = min_dim // 2

    # Cut the image into four sub-images
    sub_images = []
    for i in range(2):
        for j in range(2):
            left = i * sub_width
            upper = j * sub_height
            right = left + sub_width
            lower = upper + sub_height
            sub_img = img.crop((left, upper, right, lower))
            sub_images.append(sub_img)

    # Save each sub-image as a separate PNG file
    for i, sub_img in enumerate(sub_images):
        file_name = f"crops/{base_name}_{i + 1}.png"
        sub_img.save(file_name, "PNG")
        print(f"Saved {file_name}")


def get_document_by_field(collection_name, field_name, field_value, db):
    try:
        # Query the collection based on the specified field
        query = db.collection(collection_name).where(field_name, '==', field_value).limit(1)
        query_snapshot = query.get()

        # Check if any documents match the query
        if len(query_snapshot) == 0:
            # No matching documents found
            print('No documents found.')
            return None

        # Get the first matching document reference
        document_ref = query_snapshot[0].reference

        # Return the document reference
        return document_ref
    except Exception as e:
        print('Error getting document:', str(e))
        raise e


if __name__ == "__main__":
    # args = sys.argv[1:]
    # args = parse_args(args)
    params = os.path.abspath(os.getcwd()) + '/sender_params.json'
    local_path = os.path.abspath(os.getcwd()) + '/download'

    print('=========== listening started ===========')
    receiver = Receiver(params, local_path)
    receiver.main()
