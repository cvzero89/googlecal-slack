
import pickle
import os
from apiclient.discovery import build
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from google.auth.transport.requests import Request
import datetime
import requests
import re
import argparse
from RFC3339 import RFC3339
import logging
import re
import yaml

logging.basicConfig(filename=f'{os.path.abspath(os.path.dirname(__file__))}/calendarApp.log', encoding='utf-8', level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%d/%m/%Y %I:%M:%S %p')
parser =  argparse.ArgumentParser(description='Get Google Calendar Events → POST to Slack channel.')
parser.add_argument('frequency', help='Retrieve only events the next hour or 24 hours. Each service is configured at config.yml.', choices=['hourlyEvents', 'dailyEvents'])
parser.add_argument('team', help='Select the team calendar to use')
args = parser.parse_args()
frequency = args.frequency
team = args.team

'''
Loading config from config.yaml. The format should be:

team:
    type_of_event:
        slackURL: "string"
        calendarId: "string"
        maxResults: bool
        text: "string"
        exclude: "string"
'''

def load_config(team, frequency):
    try:
        with open(f'{os.path.abspath(os.path.dirname(__file__))}/config.yaml') as config_file:
            config = yaml.safe_load(config_file)
    except FileNotFoundError:
        print('Configuration file cannot be opened.')
        logging.debug(f'No configuration file.')
        exit()
    try:
        team_config = config[team][frequency]
        return team_config['slackURL'], team_config['calendarId'], team_config['maxResults'], team_config['text'], team_config['exclude']
    except KeyError as error_loading:
        print(f'Value not found at config file:\n{error_loading}')
        logging.debug(f'Bad config file. Please check {config}.')
        exit()

'''
Function to create the permissions to access the calendar. If the token is missing it will ask to complete sign-up via the browser.
'''

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

'''
Receives the events from the calendar and parses them into a single message to post to Slack as a block.
Can exclude events titles based on RegEx. If exclude is empty it will not exclude anything.
'''
def generate_message(events, text, exclude):
    blocks = [{
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f'{text}'
        }
    }]
    convert = RFC3339()
    for event in events:
        title = event['summary']
        event_url = event['htmlLink']
        start = event['start'].get('dateTime', event['start'].get('date'))
        
        converted_time = convert.extract_datetime(start) 
        event_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Event*: _*{title}*_ at {converted_time.strftime('%m/%d/%Y - %H:%M:%S')}"
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "View Event"
                },
                "url": event_url
            }
        }
        blocks.append(event_block)
        try:
            if event['description']:
                description = event['description']
                description = description.replace('<br>', ' ')
                description = re.sub(r'<[^>]*>', '', description)
                description_block = {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Details*: _{description}_"
                    }
                }
                blocks.append(description_block)
        except KeyError:
            print('No description added.')
    return {
        "blocks": blocks
    }

'''
Getting the events from the calendar, the ID is defined on config.yaml.
max_time is fixed to hourly or daily depending on the input to the script.
'''
def get_events(calendarId, text, maxResults, exclude, max_time, now, service):
    if maxResults == False:
        max_results = None
    else:
        max_results = maxResults
    events_list = service.events().list(calendarId=calendarId, timeMin=now, timeMax=max_time, maxResults=max_results, singleEvents=True, orderBy='startTime').execute()
    events = events_list.get('items',[])
    filtered_events = []
    print(f'Received {len(events)} events.')
    logging.info(f'Received {len(events)} events.')
    for event in events:
        title = event['summary']
        if exclude:
            exclude_regex = re.compile(exclude)
            result = exclude_regex.match(title)
            if result:
                logging.info(f'Excluded events: {title} based on set RegEx.')
                continue
        if is_event_past_one_hour(event):
            logging.info(f'Event removed: {title}, started more than 1 hour ago.')
            continue
        filtered_events.append(event)
    if not filtered_events:
        logging.info('Could not retrieve events or there are no events at this time.')
        return None
    return generate_message(filtered_events, text, exclude)

'''
Remove events if they have started more than 1 hour ago to avoid pinging the room twice with the same info for long events.
Date is converted to UTC to be able to use any timezone from GoogleCal.
'''
def is_event_past_one_hour(event):
    start_time_str = event['start'].get('dateTime', event['start'].get('date'))
    start_time = datetime.datetime.fromisoformat(start_time_str).astimezone(datetime.timezone.utc)
    current_time = datetime.datetime.now(datetime.timezone.utc)
    time_diff = current_time - start_time
    return time_diff.total_seconds() > 3600

'''
Sending the events to the webhook set at config.yaml.
The hook URL must be created at the Slack App configuration at https://api.slack.com/apps/.
'''

def send_command(message, slackURL):
    if message == None:
        print('No upcoming events found.')
    else:
        try:
            send = requests.post(slackURL, json=message)
            if send.status_code != 200:
                raise ValueError(f'Request to Slack returned an error {send.status_code}, the response is:\n{send.text}')
            else:
                logging.info(f'Message sent. HTTP code: {send.status_code}.')
                print(f'Message sent. Server response: {send.text}')
        except:
            print('Could not send message. Is the SlackURL correct?')
            logging.warning(f'Message failed: {send.text}.')
            logging.warning(f'Could not send message. Is the SlackURL correct? Message attempted to: {slackURL}')


def main():
    logging.info('Started!')
    '''
    Info to set the calendar credentials:
    '''
    client_secret_file = f'{os.path.abspath(os.path.dirname(__file__))}/calendarcredentials.json'
    api_name = 'calendar'
    api_version = 'v3'
    scopes = ['https://www.googleapis.com/auth/calendar']
    service = create_service(client_secret_file,api_name,api_version,scopes)

    '''
    Getting the current time and time delta to receive events.
    '''
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    hour = datetime.datetime.utcnow()
    hour_added = datetime.timedelta(minutes=59)
    hour_add = hour + hour_added
    day_added = datetime.timedelta(days=1)
    day_add = hour + day_added

    if frequency == 'hourlyEvents':
        slackURL, calendarId, maxResults, text, exclude = load_config(team, frequency)
        max_time = hour_add.isoformat() + 'Z'

    elif frequency == 'dailyEvents':
        slackURL, calendarId, maxResults, text, exclude = load_config(team, frequency)
        max_time = day_add.isoformat() + 'Z'

    message = get_events(calendarId, text, maxResults, exclude, max_time, now, service)
    send_command(message, slackURL)


if __name__ == "__main__":
    main()