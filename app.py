from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import re
import os

app = Flask(__name__)
app.secret_key = "dev_secret"

# DATABASE CONFIG
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

API_KEY = "03af6efdc122078edb0210097dd89939"

# ---------- DATABASE ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))

class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

# ---------- HOME ----------
@app.route("/")
def home():
    return render_template("index.html")

# ---------- MAIN API ----------
@app.route("/get_movies", methods=["POST"])
def get_movies():
    try:
        data = request.json or {}
        user_input = data.get("input", "").lower().strip()

        movies = []

        # LANGUAGE MAP
        language_map = {
            "tamil":"ta","english":"en","hindi":"hi","telugu":"te","kannada":"kn",
            "malayalam":"ml","korean":"ko","japanese":"ja","spanish":"es",
            "chinese":"zh","french":"fr","german":"de","gujarati":"gu",
            "marathi":"mr","bengali":"bn","urdu":"ur","arabic":"ar"
        }

        # GENRE MAP
        genre_map = {
            "action":28,"comedy":35,"thriller":53,
            "horror":27,"drama":18,"sci-fi":878
        }

        # NUMBER
        nums = re.findall(r'\d+', user_input)
        count = int(nums[0]) if nums else 5

        keywords = ["movie","movies","series","show"]
        is_specific = not any(word in user_input for word in keywords)

        content_type = "tv" if "series" in user_input else "movie"

        # LIKE SEARCH
        if "like" in user_input:
            name = user_input.split("like")[-1].strip()

            search = requests.get(
                f"https://api.themoviedb.org/3/search/{content_type}",
                params={"api_key": API_KEY, "query": name}
            )

            res = search.json().get("results", [])
            if res:
                movie_id = res[0]["id"]
                sim = requests.get(
                    f"https://api.themoviedb.org/3/{content_type}/{movie_id}/similar",
                    params={"api_key": API_KEY}
                )
                results = sim.json().get("results", [])[:count]
            else:
                results = []

        # SEARCH BY NAME
        elif is_specific:
            res = requests.get(
                f"https://api.themoviedb.org/3/search/{content_type}",
                params={"api_key": API_KEY, "query": user_input}
            )
            results = res.json().get("results", [])[:count]

        # SMART FILTER
        else:
            url = f"https://api.themoviedb.org/3/discover/{content_type}"
            params = {"api_key": API_KEY, "sort_by": "popularity.desc"}

            if "top" in user_input:
                params["sort_by"] = "vote_average.desc"

            year = re.search(r'20\d{2}', user_input)
            if year:
                params["primary_release_year"] = year.group()

            for l in language_map:
                if l in user_input:
                    params["with_original_language"] = language_map[l]

            for g in genre_map:
                if g in user_input:
                    params["with_genres"] = genre_map[g]

            res = requests.get(url, params=params)
            results = res.json().get("results", [])[:count]

        # FORMAT OUTPUT
        for m in results:
            poster = m.get("poster_path")
            movies.append({
                "title": m.get("title") or m.get("name"),
                "rating": m.get("vote_average"),
                "poster": f"https://image.tmdb.org/t/p/w500{poster}" if poster else ""
            })

        # SAVE HISTORY
        user_id = data.get("user_id")
        if user_id:
            db.session.add(History(query=user_input, user_id=user_id))
            db.session.commit()

        return jsonify(movies)

    except Exception as e:
        print("ERROR:", e)
        return jsonify([])

# ---------- HISTORY ----------
@app.route("/history/<int:user_id>")
def history(user_id):
    data = History.query.filter_by(user_id=user_id).order_by(History.id.desc()).all()
    return jsonify([i.query for i in data])

# ---------- AUTH ----------
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"status": "exists"})
    user = User(username=data["username"], password=generate_password_hash(data["password"]))
    db.session.add(user)
    db.session.commit()
    return jsonify({"status": "created"})

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    user = User.query.filter_by(username=data["username"]).first()
    if user and check_password_hash(user.password, data["password"]):
        return jsonify({"status": "success", "user_id": user.id})
    return jsonify({"status": "fail"})

# ---------- INIT ----------
with app.app_context():
    db.create_all()

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)