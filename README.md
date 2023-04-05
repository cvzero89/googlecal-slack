# googlecal-slack
Retrieve events from Google Calendar and post to a Slack channel.

Follow the steps from: https://developers.google.com/calendar/api/quickstart/python making sure to activate the Google Calendar API and that you will need to publish the app for Google to trust it.

Move `credentials.json` to the script folder.

First runs looks like:

```
python3 calendarApp.py dailyEvents
Creating calendar service...
Please visit this URL to authorize this application: https://accounts.google.com/o/oauth2/auth?response_type=code&client_id=-.......
Received 1 events.
Message sent. Server response: ok
```

Your browser should open to authorize the app. If not, copy the link and open it on a browser. After a successful login the script will run.

Sample of configuration file:

```
{
	"hourlyEvents": [
		{
		"slackURL": "/url/for/your/incoming/webhook",
		"calendarId": "calendarID from Google Calendar Settings",
		"maxResults": false,
		"text": "Text to display before listing events",
		"exclude": "reGex to exclude events titles, separate with | if multiple strings"
		}
	],
	"dailyEvents": [
		{
		"slackURL": "/url/for/your/incoming/webhook",
		"calendarId": "calendarID from Google Calendar Settings",
		"maxResults": false,
		"text": "Text to display before listing events",
		"exclude": "reGex to exclude events titles, separate with | if multiple strings"			
		}
	]
}
```

`slackURL` can be created by following the steps on this link: https://api.slack.com/messaging/webhooks. <br>
`calendarId` can be retrieved from the Google Calendar > Settings > Settings for calendars. Main calendars are called `primary`. <br>
`maxResults` limit the number of events to show. If set to False it will get all available events during the task timeframe. <br>
`text` Text to add at the top of the message in Slack. <br>
`exclude` using reGex to remove events.
