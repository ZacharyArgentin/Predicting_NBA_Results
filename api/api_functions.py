import pandas as pd
import requests
from datetime import date
from datetime import timedelta
import time




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
        for page_num in range(2, n_pages + 1):
            # Make sure not to exceed the 60 request per second limit
            time.sleep(1)
        # The code is slightly different depending on whether the query paramerters were passed
        # as a dictionary or as a list of tuples
            if isinstance(params, dict):
                params.update({"page": page_num})
                response = requests.get(root + endpoint, params=params)
                page_n = pd.json_normalize(response.json(), record_path=record_path)
                df = df.append(page_n)
            if isinstance(params, list):
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

    # Ensure that the ids are integers
    home_team_id = int(home_team_id)
    away_team_id = int(away_team_id)

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
    


    
    def format_params(game_ids):
        """ 
        Format query paramaters in a format the balldontlie API accepts
        e.g. ?game_ids[]=345686&game_ids[]=234356&gameids[]=3456356...
        """
        params = "game_ids[] " * len(game_ids)
        params = list(zip(params.split(" "), game_ids))
        params.append(("per_page", 100))
        return params
    
    stats_cols = ["ast","blk","dreb","fg3_pct","fg3a","fg3m","fg_pct","fga","fgm","ft_pct","fta","ftm","oreb",
              "pf","pts","reb","stl","turnover"]
    
    # Get pandas Series of home team stats
    params_home = format_params(game_ids_home)                                 # Get param list
    stats_home = make_request("stats", record_path="data", params=params_home) # Make request with said param list
    stats_home = clean_stats(stats_home)                                       # clean the data
    stats_home = stats_home[stats_home["team.id"].eq(stats_home["game.home_team_id"])]  # Filter for stats of players that played for the home team
    stats_home = aggregate_stats(stats_home)                                   # aggregate individual player stats into team stats
    stats_home = stats_home[stats_cols]                                        # Drop the columns that aren't basketball stats
    stats_home = stats_home.mean()                                             # average the stats
    
    # Get pandas Series of away team stats
    params_away = format_params(game_ids_away)
    stats_away = make_request("stats", record_path="data", params=params_away)
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
    
    stats = stats_home.append([stats_away, stats_diff])
    model_input = stats.values.reshape(1,-1)
    
    return model_input




def get_team_code_map(df=False):
    # Make balldontlie api request and convert the json response to pandas dataframe
    team_code_df = make_request("teams", record_path="data")
    team_code_df = team_code_df[["id", "city", "abbreviation", "full_name", "name"]]
    team_code_df = team_code_df.set_index("id")
    # using said dataframe, map team names to team id
    team_code_map = {}
    for row in team_code_df.iterrows():
        team_code_map.update(dict.fromkeys(row[1].str.lower().values, row[0]))
        # Make sure "1" maps to 1. i.e. string maps to integer. This is so people can enter the team code
        # in the text box for convenience and everything still works fine.
        team_code_map.update({str(row[0]): row[0]})                   
    if df:
        return team_code_df
    else:
        return team_code_map  # returning a dictionary