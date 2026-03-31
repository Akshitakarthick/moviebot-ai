from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import requests, re, os

app = Flask(__name__)
CORS(app)

app.secret_key = "dev_secret"

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
        data = request.get_json(force=True)
        user_input = data.get("input", "").lower().strip()

        movies = []

        # 🌍 LANGUAGE MAP
        language_map = {
            "tamil":"ta","english":"en","hindi":"hi","telugu":"te","kannada":"kn",
            "malayalam":"ml","korean":"ko","japanese":"ja","spanish":"es",
            "chinese":"zh","french":"fr","german":"de"
        }

        # 🎬 MOVIE GENRES
        movie_genres = {
            "action":28,"comedy":35,"thriller":53,
            "horror":27,"drama":18,"sci-fi":878
        }

        # 📺 TV GENRES
        tv_genres = {
            "action":10759,"comedy":35,"thriller":9648,
            "horror":9648,"drama":18,"sci-fi":10765
        }

        # 🔢 NUMBER
        nums = re.findall(r'\d+', user_input)
        count = int(nums[0]) if nums else 5

        # 🎯 TYPE DETECTION
        if any(x in user_input for x in ["series","webseries","show"]):
            content_type = "tv"
            current_genres = tv_genres
        else:
            content_type = "movie"
            current_genres = movie_genres

        url = f"https://api.themoviedb.org/3/discover/{content_type}"

        params = {
            "api_key": API_KEY,
            "sort_by": "popularity.desc"
        }

        # ⭐ TOP
        if "top" in user_input or "best" in user_input:
            params["sort_by"] = "vote_average.desc"

        # 📅 YEAR
        year = re.search(r'20\d{2}', user_input)
        if year:
            params["primary_release_year"] = year.group()

        # 🌍 LANGUAGE DETECTION
        language_found = None
        for l in language_map:
            if l in user_input:
                language_found = language_map[l]
                params["with_original_language"] = language_found
                break

        # 🎭 MULTI GENRE
        genres = []
        for g in current_genres:
            if g in user_input:
                genres.append(str(current_genres[g]))

        if genres:
            params["with_genres"] = ",".join(genres)

        # ---------- TRY 1 ----------
        res = requests.get(url, params=params)
        results = res.json().get("results", [])

        # ---------- TRY 2 (REMOVE LANGUAGE) ----------
        if not results and language_found:
            temp = params.copy()
            temp.pop("with_original_language", None)

            res = requests.get(url, params=temp)
            results = res.json().get("results", [])

        # ---------- TRY 3 (REMOVE GENRE ALSO) ----------
        if not results:
            temp = params.copy()
            temp.pop("with_original_language", None)
            temp.pop("with_genres", None)

            res = requests.get(url, params=temp)
            results = res.json().get("results", [])

        results = results[:count]

        # ---------- FORMAT ----------
        for m in results:
            poster = m.get("poster_path")
            movies.append({
                "title": m.get("title") or m.get("name"),
                "rating": m.get("vote_average"),
                "poster": f"https://image.tmdb.org/t/p/w500{poster}" if poster else ""
            })

        # ---------- SAVE HISTORY ----------
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

# ---------- SIGNUP ----------
@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(force=True)

    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"status": "exists"})

    user = User(
        username=data["username"],
        password=generate_password_hash(data["password"])
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({"status": "created"})

# ---------- LOGIN ----------
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True)

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
