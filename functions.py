import pandas as pd
import requests
from datetime import date
from datetime import timedelta


def make_request(endpoint, params=None, record_path=None, verbose=False):
    root = "https://www.balldontlie.io/api/v1/"
    response = requests.get(root + endpoint, params=params)
    if response.status_code != 200:
        print(response.status_code)
        return response
    if verbose: 
        print("Success!")  
    df = pd.json_normalize(response.json(), record_path=record_path)
   
    # If the request ends up being a multi page request, get all the pages
    # and then complile the results into one dataframe
    n_pages = response.json()["meta"]["total_pages"] 
    if n_pages > 1:
        if isinstance(params, dict):
            for page_num in range(2, n_pages + 1):
                params.update({"page": page_num})
                response = requests.get(root + endpoint, params=params)
                page_n = pd.json_normalize(response.json(), record_path=record_path)
                df = df.append(page_n)
        if isinstance(params, list):
            for page_num in range(2, n_pages + 1):
                params.append(("page", page_num))
                response = requests.get(root + endpoint, params=params)
                page_n = pd.json_normalize(response.json(), record_path=record_path)
                df = df.append(page_n)
                params.pop()
            
    return df


def get_recent_games(home_team_id, away_team_id):
    """
    Get a list game ids for the 20 most recent games played for each team specified.

    ---Params---
    home_team_id: int
    away_team_id: int

    ---Returns---
     a tuple of 2 lists. ---> ([home team game ids], [away team game ids])
    """
    # Get todays date
    today = date.today()                                                           # Get today
    today = f"{today.year}-{today.month}-{today.day}"                              # Convert to format yyyy-mm-dd
    one_year_ago = date.today() - timedelta(days=365)                              # Get last-year-today
    one_year_ago = f"{one_year_ago.year}-{one_year_ago.month}-{one_year_ago.day}"  # convert to format yyyy-mm-dd

    # get home team recent games
    recent_games_home = pd.DataFrame()
    res = make_request("games", record_path="data", params={"end_date": today,
                                                            "start_date": one_year_ago,
                                                            "team_ids[]": [home_team_id],
                                                            "page": 1,
                                                            "per_page": "100"})
    res = res.sort_values("date", ascending=False)
    res = res[res["home_team.id"].eq(home_team_id)]

    recent_games_home = recent_games_home.append(res)
    recent_games_home = recent_games_home.head(20)
    game_ids_home = list(recent_games_home["id"].values)

    # get away team recent games
    recent_games_away = pd.DataFrame()
    res = make_request("games", record_path="data", params={"end_date": "2021-11-09",
                                                            "start_date": "2020-11-09",
                                                            "team_ids[]": [away_team_id],
                                                            "page": 1,
                                                            "per_page": "100"})

    res = res.sort_values("date", ascending=False)
    res = res[res["visitor_team.id"].eq(away_team_id)]

    recent_games_away = recent_games_away.append(res)
    recent_games_away = recent_games_away.head(20)
    game_ids_away = list(recent_games_away["id"].values)


    return game_ids_home, game_ids_away