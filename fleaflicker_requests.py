# get league data from fleaflicker API using python requests

import requests
import pandas as pd
import json

api_url = 'https://www.fleaflicker.com/api'

table_name = '/FetchRoster'

league_id = 'league_id=78455'

sport = 'sport=NFL'

season = 'season=2023'

scoring_period = 'scoring_period=17'

week = 'week=17'

team_id = 'team_id=689370'

full_string = api_url + table_name + '?' + league_id  + '&' + team_id #+'&' + season + '&' + scoring_period
#full_string = 'https://jsonplaceholder.typicode.com/todos/1'
print(full_string)

response  = requests.get(full_string)
data = json.load(response.json())

print(response)

#print(response.json())
#print(response.status_code)
#print(response.headers["Content-Type"])

df_idk = pd.read_json(data)

print(df_idk.head())



