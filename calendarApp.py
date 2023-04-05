
import pickle
import os
from apiclient.discovery import build
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from google.auth.transport.requests import Request
import datetime
import requests
import json
import re
import argparse
from RFC3339 import RFC3339
import logging

logging.basicConfig(filename=f'{os.path.abspath(os.path.dirname(__file__))}/calendarApp.log', encoding='utf-8', level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%d/%m/%Y %I:%M:%S %p')
parser =  argparse.ArgumentParser(description='Get Google Calendar Events → POST to Slack channel.')
parser.add_argument('frequency', help='Retrieve only events the next hour or 24 hours. Each service is configured at .config.json.', choices=['hourlyEvents', 'dailyEvents'])
args = parser.parse_args()
frequency = args.frequency

client_secret_file = f'{os.path.abspath(os.path.dirname(__file__))}/calendarcredentials.json'
api_name = 'calendar'
api_version = 'v3'
scopes = ['https://www.googleapis.com/auth/calendar']

def load_config(frequency):
    config = open(f'{os.path.abspath(os.path.dirname(__file__))}/.config.json')
    try:
        config_file = json.load(config)
        loaded_keys = list(config_file[frequency])
        return loaded_keys
    except ValueError as error_loading:
        print(f'Error decoding JSON file!\n{error_loading}')
        logging.debug(f'Malformed JSON file. Please check {config}.')
        exit()

def create_service(client_secret_file, api_name, api_version, *scopes):
    print('Creating calendar service...')
    cred = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    CLIENT_SECRET_FILE = client_secret_file
    API_SERVICE_NAME = api_name
    API_VERSION = api_version
    SCOPES = [scope for scope in scopes[0]]
    pickle_file = f'{os.path.abspath(os.path.dirname(__file__))}/token_{API_SERVICE_NAME}_{API_VERSION}.pickle'
    if os.path.exists(pickle_file):
        with open(pickle_file, 'rb') as token:
            cred = pickle.load(token)

    if not cred or not cred.valid:
        logging.warning('Calendar credentials are not here/valid. Requesting again.')
        if cred and cred.expired and cred.refresh_token:
            cred.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            cred = flow.run_local_server()

        with open(pickle_file, 'wb') as token:
            pickle.dump(cred, token)

    try:
        service = build(API_SERVICE_NAME, API_VERSION, credentials=cred)
        return service
    except Exception as e:
        print(e)
        logging.debug(f'Error creating calendar service: {e}')
        return None
service = create_service(client_secret_file,api_name,api_version,scopes)

now = datetime.datetime.utcnow().isoformat() + 'Z'
hour = datetime.datetime.utcnow()
hour_added = datetime.timedelta(hours=1)
hour_add = hour + hour_added
day_added = datetime.timedelta(days=1)
day_add = hour + day_added

def generate_message(events, text, exclude_list):
    blocks = [{
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f'{text}'
        }
    }]
    for event in events:
        title = event['summary']
        exclude_regex = re.compile(exclude_list)
        result = exclude_regex.match(title)
        if result:
            logging.info('Excluded events based on set RegEx.')
            continue
        event_url = event['htmlLink']
        start = event['start'].get('dateTime', event['start'].get('date'))
        convert = RFC3339()
        converted_time = convert.extract_datetime(start) 
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{title}* at {converted_time.strftime('%m/%d/%Y, %H:%M:%S')}"
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "View Event"
                },
                "url": event_url
            }
        })

    return {
        "blocks": blocks
    }


def get_events(loaded_config, max_time):
    calendarId = loaded_config[0]['calendarId']
    text = loaded_config[0]['text']
    if loaded_config[0]['maxResults'] == False:
        max_results = None
    else:
        max_results = loaded_config[0]['maxResults']
    events_list = service.events().list(calendarId=calendarId, timeMin=now, timeMax=max_time, maxResults=max_results, singleEvents=True, orderBy='startTime').execute()
    events = events_list.get('items',[])
    exclude_list = loaded_config[0]['exclude']
    if not events:
        logging.info('Could not retrieve events or there are no events at this time.')
        return None
    else:
        print(f'Received {len(events)} events.')
        logging.info(f'Received {len(events)} events.')
    return generate_message(events, text, exclude_list)

def send_command(message, slackURL):
    if message == None:
        print('No upcoming events found.')
    else:
        send = requests.post(slackURL, json=message)
        if send.status_code != 200:
            raise ValueError(f'Request to Slack returned an error {send.status_code}, the response is:\n{send.text}')
        else:
            logging.info(f'Message sent. HTTP code: {send.status_code}.')
            print(f'Message sent. Server response: {send.text}') 


def main():
    logging.info('Started!')
    if frequency == 'hourlyEvents':
        loaded_config = load_config(frequency)
        slackURL = loaded_config[0]['slackURL']
        max_time = hour_add.isoformat() + 'Z'
        message = get_events(loaded_config, max_time)
        send_command(message, slackURL)
    elif frequency == 'dailyEvents':
        loaded_config = load_config(frequency)
        max_time = day_add.isoformat() + 'Z'
        slackURL = loaded_config[0]['slackURL']
        message = get_events(loaded_config, max_time)
        send_command(message, slackURL)


if __name__ == "__main__":
    main()
