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


def clean_stats(df):
    # drop columns with superfluous information
    df.drop(["id", "game.period", "game.postseason", "game.status", "game.time", "player.height_feet", "player.height_inches",
            "player.weight_pounds", "team.abbreviation", "team.city", "team.conference", "team.division", "team.name",
            "player.first_name", "player.last_name", "player.position", "team.full_name", "player.team_id"],
          axis=1, inplace=True)
    
    # drop rows with any null values
    # a null value generally indicates that the player did not play in that game
    df.dropna(axis=0, how="any", inplace=True)
    
    
    ### Dealing with time
    # clean time column to get a consitent format. ("mm:ss" or "m:ss")
    
    df["min"] = df["min"].astype(str)

    # drop the row if the player didn't play in the game
    played_0min = df[df["min"].eq("0:00") | df["min"].eq("") | df["min"].str.startswith("0")].index
    df.drop(played_0min, axis=0, inplace=True)

    # Convert times like "27.0" to "27:0"
    df["min"] = df["min"].str.replace(".",":")

    # convert times like "27" to "27:00"
    minutes_only_times = df["min"][~df["min"].str.contains(":")].index
    df["min"].loc[minutes_only_times] += ":00"


    minutes = [time[0] for time in df["min"].str.split(":").values]
    seconds = [time[1] for time in df["min"].str.split(":").values]

    # convert times like "27:0" to "27:00"
    for i, second in enumerate(seconds):
        if len(second) == 1:
            seconds[i] = second + "0"

    # convert times like "8:60" to "9:00"
    for i, second in enumerate(seconds):        
        if second == "60":
            seconds[i] = "00"
            minutes[i] = str(int(minutes[i]) + 1)  # increment minutes by 1

    times = [":".join(list(item)) for item in list(zip(minutes,seconds))]

    df["min"] = times
    
    return df


def aggregate_stats(df):
    # Convert game date to datetime
    df["game.date"] = pd.to_datetime(df["game.date"]).dt.tz_localize(None)

    # Convert string to timedelta
    df["min"] = [pd.Timedelta(minutes=int(time[0]), seconds=int(time[1])) for time in df["min"].str.split(":").values]

    agg_map = {"ast": "sum", 
           "blk": "sum", 
           "dreb": "sum", 
           "fg3_pct": "mean", 
           "fg3a": "sum", 
           "fg3m": "sum", 
           "fg_pct": "mean",
          "fga": "sum",
          "fgm": "sum",
          "ft_pct": "mean",
          "fta": "sum",
          "ftm": "sum",
          "min": "sum",
          "oreb": "sum",
          "pf": "sum",
          "pts": "sum",
          "reb": "sum",
          "stl": "sum",
          "turnover": "sum",
          "game.id": "first",
          "game.date": "first",
          "game.season": "first",
          "game.home_team_id": "first",
          "game.home_team_score": "first",
          "game.visitor_team_id": "first",
          "game.visitor_team_score": "first",
          "player.id": "first",
          "team.id": "first",}

    df = df.groupby("game.id").agg(agg_map)

    return df

