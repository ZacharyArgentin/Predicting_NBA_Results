import pandas as pd
import requests
from datetime import date
from datetime import timedelta
import time
import os




def make_request(endpoint, next_cursor=0, params=None, verbose=False):
    root = "https://api.balldontlie.io/v1/"
    api_key = os.environ["BALLDONTLIE_API_KEY"]
    headers = {"Authorization": api_key}
    if params is None: params = {}
    # This API uses cursor based pagination.
    # The cursor should be initialized to 0 so that the first requests will fetch the first page.
    # If there is more than one page to the request, the response will include a "next_cursor" attribute in 
    # the meta data JSON.
    # In the next request, set the cursor parameter to this number to get the next page
    if verbose: print("Starting Loop")
    df_list = []
    request_count = 0
    while next_cursor is not None:
        if verbose: print("Making request... ")
        response = requests.get(root + endpoint, headers=headers, params=params)
        request_count += 1
        if response.status_code != 200:
            print(f"Request failed: {response.status_code}")
            break
        if verbose: print(f"Request Succeeded - {response.status_code}" )
        res = response.json()
        data = res["data"]
        if data:
            df_list.append(pd.json_normalize(data))
        meta_data = res.get("meta", None)
        if meta_data is None:  # Enpoint doesn't support pagination, no need to loop
            break
        next_cursor = meta_data.get("next_cursor")
        if next_cursor is None:  # Last page reached, no need to loop
            break
        params.update({"cursor": next_cursor})
        # Max 60 requests per minute, sleep if necessary
        if request_count % 60 == 0:
            print("Max 60 requests per minute, sleeping for 60 seconds..")
            time.sleep(60)
    # Concatenate all collected data into one DataFrame
    if df_list:
        return pd.concat(df_list)
    else:
        return pd.DataFrame()




def get_recent_games(home_team_id, away_team_id):
    """
    Get a list game ids for the 20 most recent games played for each team specified.

    ---Params---
    home_team_id: int
    away_team_id: int

    ---Returns---
     a tuple of 2 lists. ---> ([home team game ids], [away team game ids])
    """

    # Ensure that the ids are integers
    home_team_id = int(home_team_id)
    away_team_id = int(away_team_id)

    # Get todays date
    today = date.today()                               # Get today
    today = today.strftime("%Y-%m-%d")                 # Convert to format yyyy-mm-dd
    one_year_ago = date.today() - timedelta(days=365)  # Get last-year-today
    one_year_ago = one_year_ago.strftime("%Y-%m-%d")   # convert to format yyyy-mm-dd

    # get home team recent games
    recent_games_home = pd.DataFrame()
    res = make_request("games", params={"end_date": today,
                                        "start_date": one_year_ago,
                                        "team_ids[]": [home_team_id, 0],  # No idea how requests is bulding the query string, but the api is throwing a "invalid value" error when there's only one value, so need to pass a dummy value of 0 to get it to work
                                        "per_page": "100"})
    res = res.sort_values("date", ascending=False)
    res = res[res["home_team.id"].eq(home_team_id)]

    recent_games_home = pd.concat([recent_games_home, res])
    recent_games_home = recent_games_home.head(20)
    game_ids_home = list(recent_games_home["id"].values)

    # get away team recent games
    recent_games_away = pd.DataFrame()
    res = make_request("games", params={"end_date": "2021-11-09",
                                        "start_date": "2020-11-09",
                                        "team_ids[]": [away_team_id, 0],  # No idea how requests is bulding the query string, but the api is throwing a "invalid value" error when there's only one value, so need to pass a dummy value of 0 to get it to work
                                        "per_page": "100"})

    res = res.sort_values("date", ascending=False)
    res = res[res["visitor_team.id"].eq(away_team_id)]

    recent_games_away = pd.concat([recent_games_away, res])
    recent_games_away = recent_games_away.head(20)
    game_ids_away = list(recent_games_away["id"].values)


    return game_ids_home, game_ids_away




def clean_stats(df):
    # drop columns with superfluous information
    df.drop(["id", "game.period", "game.postseason", "game.status", "game.time", "player.height",
            "player.weight", "team.abbreviation", "team.city", "team.conference", "team.division", "team.name",
            "player.first_name", "player.last_name", "player.position", "team.full_name", "player.team_id"],
          axis=1, inplace=True)
    
    # Some responses have a mysterious "player" column with all null values
    # It's important to remove this column if it exists, otherwise the next block
    # of code will drop every single row and will produce errors
    try: 
        df.drop("player", axis=1, inplace=True)
    except KeyError:
        pass
    
    # drop rows with any null values
    # a null value generally indicates that the player did not play in that game
    df.dropna(axis=0, how="any", inplace=True)
    
    
    ### Dealing with time
    # clean time column to get a consitent format. ("mm:ss" or "m:ss")
    
    df["min"] = df["min"].astype(str)

    # drop the row if the player didn't play in the game
    df.reset_index(drop=True, inplace=True)  # The next line of code depends on unique indices!!!!
    played_0min = df[df["min"].eq("0:00") | df["min"].eq("") | df["min"].str.startswith("0")].index
    df.drop(played_0min, axis=0, inplace=True)

    # Convert times like "27.0" to "27:0"
    df["min"] = df["min"].str.replace(".",":", regex=False)

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




def get_stats(game_ids_home, game_ids_away):
    """
    This function makes a request to balldontlie API for stats from specific games.
    The arguments for this function should be:
    1. a list of the 20 most recent game ids for the home team
    2. a list of the 20 most recent game ids for the away team
    
    The order matters. Putting the away team as the first argument and home team as the
    second will produce inaccurate results.
    
    The function returns a Numpy array that the model is expecting as input.
    """
    
    
    stats_cols = ["ast","blk","dreb","fg3_pct","fg3a","fg3m","fg_pct","fga","fgm","ft_pct","fta","ftm","oreb",
              "pf","pts","reb","stl","turnover"]
    
    # Get pandas Series of home team stats
    stats_home = make_request("stats", params={
            "game_ids": game_ids_home,
            "per_page": 100
        })
    stats_home = clean_stats(stats_home)                                       
    stats_home = stats_home[stats_home["team.id"].eq(stats_home["game.home_team_id"])]  # Filter for stats of players that played for the home team
    stats_home = aggregate_stats(stats_home)                                   # aggregate individual player stats into team stats
    stats_home = stats_home[stats_cols]                                        # Drop the columns that aren't basketball stats
    stats_home = stats_home.mean()                                             # average the stats
    
    # Get pandas Series of away team stats
    stats_away = make_request("stats", params={
            "game_ids": game_ids_away,
            "per_page": 100
        })
    stats_away = clean_stats(stats_away)
    stats_away = stats_away[stats_away["team.id"].eq(stats_away["game.visitor_team_id"])]
    stats_away = aggregate_stats(stats_away)
    stats_away = stats_away[stats_cols]
    stats_away = stats_away.mean()
    
    # Make a stats diff Series
    stats_diff = stats_home - stats_away
    
    # Rename columns and put it all together
    stats_home.index = "home_" + stats_home.index
    stats_away.index = "away_" + stats_away.index
    stats_diff.index = "diff_" + stats_diff.index
    
    stats = pd.concat([stats_home, stats_away, stats_diff])
    model_input = stats.values.reshape(1,-1)
    
    return model_input




def get_team_code_map(df=False):
    # Make balldontlie api request and convert the json response to pandas dataframe
    team_code_df = make_request("teams")
    team_code_df = team_code_df[["id", "city", "abbreviation", "full_name", "name"]]
    team_code_df = team_code_df.set_index("id")
    # using said dataframe, map team names to team id
    team_code_map = {}
    for row in team_code_df.iterrows():
        # Make sure "1" maps to 1. i.e. string maps to integer. 
        # This is so people can enter the team code in the 
        # text box for convenience and everything still works fine.
        team_code_map.update({str(row[0]): row[0]})
        # map the rest of the valid inputs to the team id 
        team_code_map.update(dict.fromkeys(row[1].str.lower().values, row[0]))                  
    if df:
        return team_code_df
    else:
        return team_code_map  # returning a dictionary