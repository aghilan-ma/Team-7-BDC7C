"""
Spring Music - Python/Flask equivalent of the Spring Boot application.

Install dependencies:
    pip install flask flask-sqlalchemy flask-cors

Run:
    python app.py
    python app.py --profile mysql
    python app.py --profile postgres
"""

import argparse
import json
import os
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path

from flask import Flask, jsonify, request, abort
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Profile / database configuration  (mirrors application.yml)
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--profile", default="in-memory",
                    choices=["in-memory", "mysql", "postgres"],
                    help="Database profile to activate")
args, _ = parser.parse_known_args()
ACTIVE_PROFILE = os.environ.get("SPRING_PROFILES_ACTIVE", args.profile)

PROFILES = {
    "in-memory": "sqlite:///:memory:",
    "mysql":     "mysql+pymysql://root:@localhost/music",
    "postgres":  "postgresql://postgres:@localhost/music",
}

app.config["SQLALCHEMY_DATABASE_URI"] = PROFILES.get(ACTIVE_PROFILE, PROFILES["in-memory"])
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ---------------------------------------------------------------------------
# Domain model  (Album.java)
# ---------------------------------------------------------------------------

class Album(db.Model):
    __tablename__ = "album"

    id          = db.Column(db.String(40), primary_key=True, default=lambda: str(uuid.uuid4()))
    title       = db.Column(db.String(255))
    artist      = db.Column(db.String(255))
    release_year = db.Column("releaseYear", db.String(10))
    genre       = db.Column(db.String(100))
    track_count = db.Column("trackCount", db.Integer, default=0)
    album_id    = db.Column("albumId", db.String(40))

    def to_dict(self):
        return {
            "id":          self.id,
            "title":       self.title,
            "artist":      self.artist,
            "releaseYear": self.release_year,
            "genre":       self.genre,
            "trackCount":  self.track_count,
            "albumId":     self.album_id,
        }

    @staticmethod
    def from_dict(data):
        return Album(
            id          = data.get("id") or str(uuid.uuid4()),
            title       = data.get("title"),
            artist      = data.get("artist"),
            release_year = data.get("releaseYear"),
            genre       = data.get("genre"),
            track_count = data.get("trackCount", 0),
            album_id    = data.get("albumId"),
        )

# ---------------------------------------------------------------------------
# Repository populator  (AlbumRepositoryPopulator.java)
# Loads albums.json on startup if the table is empty.
# ---------------------------------------------------------------------------

def populate_albums():
    if Album.query.count() > 0:
        return
    albums_file = Path(__file__).parent / "src/main/resources/albums.json"
    if not albums_file.exists():
        return
    with open(albums_file) as f:
        records = json.load(f)
    for rec in records:
        album = Album(
            id           = str(uuid.uuid4()),
            title        = rec.get("title"),
            artist       = rec.get("artist"),
            release_year = rec.get("releaseYear"),
            genre        = rec.get("genre"),
            track_count  = rec.get("trackCount", 0),
        )
        db.session.add(album)
    db.session.commit()
    print(f"[AlbumRepositoryPopulator] Loaded {len(records)} albums from albums.json")

# ---------------------------------------------------------------------------
# ApplicationInfo  (ApplicationInfo.java + InfoController.java)
# ---------------------------------------------------------------------------

@dataclass
class ApplicationInfo:
    profiles: list
    services: list

def get_app_info():
    return ApplicationInfo(
        profiles=[ACTIVE_PROFILE],
        services=[],
    )

# ---------------------------------------------------------------------------
# Album REST controller  (AlbumController.java — /albums)
# ---------------------------------------------------------------------------

@app.route("/albums", methods=["GET"])
def list_albums():
    """GET /albums — return all albums."""
    albums = Album.query.all()
    return jsonify([a.to_dict() for a in albums])


@app.route("/albums/<string:album_id>", methods=["GET"])
def get_album(album_id):
    """GET /albums/{id} — return a single album."""
    album = Album.query.get(album_id)
    if album is None:
        abort(404)
    return jsonify(album.to_dict())


@app.route("/albums", methods=["PUT"])
def add_album():
    """PUT /albums — add a new album."""
    data = request.get_json(force=True)
    album = Album.from_dict(data)
    db.session.add(album)
    db.session.commit()
    print(f"[AlbumController] Adding album {album.id}")
    return jsonify(album.to_dict()), 201


@app.route("/albums", methods=["POST"])
def update_album():
    """POST /albums — update an existing album."""
    data = request.get_json(force=True)
    album = Album.query.get(data.get("id"))
    if album is None:
        abort(404)
    album.title       = data.get("title", album.title)
    album.artist      = data.get("artist", album.artist)
    album.release_year = data.get("releaseYear", album.release_year)
    album.genre       = data.get("genre", album.genre)
    album.track_count = data.get("trackCount", album.track_count)
    album.album_id    = data.get("albumId", album.album_id)
    db.session.commit()
    print(f"[AlbumController] Updating album {album.id}")
    return jsonify(album.to_dict())


@app.route("/albums/<string:album_id>", methods=["DELETE"])
def delete_album(album_id):
    """DELETE /albums/{id} — delete an album."""
    album = Album.query.get(album_id)
    if album is None:
        abort(404)
    db.session.delete(album)
    db.session.commit()
    print(f"[AlbumController] Deleting album {album_id}")
    return "", 204


# ---------------------------------------------------------------------------
# Info controller  (InfoController.java — /appinfo)
# ---------------------------------------------------------------------------

@app.route("/appinfo", methods=["GET"])
def app_info():
    """GET /appinfo — returns active profiles and services."""
    info = get_app_info()
    return jsonify({"profiles": info.profiles, "services": info.services})


# ---------------------------------------------------------------------------
# Error controller  (ErrorController.java — /errors/*)
# ---------------------------------------------------------------------------

@app.route("/errors/throw", methods=["GET"])
def throw_error():
    """GET /errors/throw — raises a runtime exception."""
    raise RuntimeError("Simulated NullPointerException")


@app.route("/errors/kill", methods=["GET"])
def kill_app():
    """GET /errors/kill — shuts down the application."""
    os._exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        populate_albums()

    print(f"[Spring Music] Active profile : {ACTIVE_PROFILE}")
    print(f"[Spring Music] Database       : {app.config['SQLALCHEMY_DATABASE_URI']}")
    print("[Spring Music] Starting on    : http://localhost:8080")
    app.run(host="0.0.0.0", port=8080, debug=True)
