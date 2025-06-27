from flask import Flask, render_template, request
import pickle
from api_functions import *

app = Flask(__name__)

team_df = make_request("teams")
teams = team_df.to_dict(orient="records") # list of dictionaries


# Load the trained model
model = pickle.load(open("model.sav", "rb"))

# defining what happens on the home page
@app.route("/", methods=["POST", "GET"])
def index():
    # After submitting the form...
    if request.method == "POST":
        home_id = int(request.form["homeTeam"])
        away_id = int(request.form["awayTeam"])

        
        # Make the appropriate balldontlie api calls
        home_game_ids, away_game_ids = get_recent_games(home_id, away_id)
        model_input = get_stats(home_game_ids, away_game_ids)
        # let the trained model make a prediction (1 for home win, 0 for away win)
        pred = model.predict(model_input)
        # Get the name of the winning team
        # Also get confidence (percent chance of winning)
        if int(pred) == 1:
            winner = teams[home_id - 1]["full_name"]
            confidence = round(100 * model.predict_proba(model_input)[0][1])
        if int(pred) == 0:
            winner = teams[away_id - 1]["full_name"]
            confidence = round(100 * model.predict_proba(model_input)[0][0])
        # Display the home page with the prediction
        return render_template("index.html", winner=winner, confidence=confidence, teams=teams)
    else:
        # Display the home page 
        # (runs only when the website is first loaded)
        return render_template("index.html", teams=teams)

if __name__ == "__main__":
    app.run(debug=True)