import pandas as pd
import requests


def make_request(endpoint, params=None, record_path=None, verbose=False):
    root = "https://www.balldontlie.io/api/v1/"
    response = requests.get(root + endpoint, params=params)
    if response.status_code != 200:
        print(response.status_code)
        return response
    if verbose: 
        print("Success!")
    res = response.json()
    res = pd.json_normalize(res, record_path=record_path)
    return res


def get_recent_games(home_team_id, away_team_id):
    """
    Get a list game ids for the 20 most recent games played for each team specified.
    Returns a tuple of 2 lists. ---> ([home team game ids], [away team game ids])
    """
    # get home team recent games
    recent_games_home = pd.DataFrame()
    res = make_request("games", record_path="data", params={"end_date": "2021-11-09",
                                                            "start_date": "2020-11-09",
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