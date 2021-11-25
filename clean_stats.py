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
    played_0min = df[df["min"].eq("0:00") | df["min"].str.startswith("0")].index
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