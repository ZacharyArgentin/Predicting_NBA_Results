from flask import Flask, render_template, request
import pickle
from api_functions import *

app = Flask(__name__)

# Load the team name map
name_map = get_team_code_map()

# get a list of valid inputs to display on the webpage
input_table = list(name_map.keys())
# Each team can be referred to by 5 valid inputs
# To display these inputs nicely using flask, we have to organize
# the list of strings so that there is 1 string per team instead
# of 1 string per input
# e.g
# ["atlanta", "hawks", "boston", "celtics"] --> ["atlanta, hawks", "boston celtics"] 
for i in range(len(input_table), 0, -5):
    input_table.insert(i, "\n")           # add a newline character where we want to split
input_table = " , ".join(input_table)       # join to one big long string
input_table = input_table.split(", \n ,")     # split where we added the newlines

# Load the trained model
model = pickle.load(open("model.sav", "rb"))

# defining what happens on the home page
@app.route("/", methods=["POST", "GET"])
def index():
    # After submitting the form...
    if request.method == "POST":
        # Assign the input of the text boxes to variables
        home_team_name = request.form["homeTeam"]
        away_team_name = request.form["awayTeam"]
        # Clean input
        home_team_name = home_team_name.lower()
        away_team_name = away_team_name.lower()
        # Convert the input to the appropriate team id
        home_id = name_map[home_team_name]
        away_id = name_map[away_team_name]
        
        # Make the appropriate balldontlie api calls
        home_game_ids, away_game_ids = get_recent_games(home_id, away_id)
        model_input = get_stats(home_game_ids, away_game_ids)
        # let the trained model make a prediction (1 for home win, 0 for away win)
        pred = model.predict(model_input)
        # Get the name of the winning team
        # Also get confidence (percent chance of winning)
        if int(pred) == 1:
            # This is kind of a hack to get the full name of the team from the name map
            # as the home id is a value and the name is a key. And also there are multiple
            # keys for the same value
            winner = list(name_map)[home_id * 5 - 2].title()
            confidence = round(100 * model.predict_proba(model_input)[0][1])
        if int(pred) == 0:
            winner = list(name_map)[away_id * 5 - 2].title()
            confidence = round(100 * model.predict_proba(model_input)[0][0])
        # Display the home page with the prediction
        return render_template("index.html", winner=winner, confidence=confidence, inputTable=input_table)
    else:
        # Display the home page 
        # (runs only when the website is first loaded)
        return render_template("index.html", inputTable=input_table)

if __name__ == "__main__":
    app.run(debug=True)