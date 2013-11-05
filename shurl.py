import os
import string
import urllib2
import binascii
import json
import math
from sqlite3 import dbapi2 as sqlite3
from flask import Flask, request,  g, redirect, url_for, abort, render_template, jsonify
from wtforms import Form, StringField, validators


CURRPATH = os.path.dirname(os.path.realpath(__file__))
app = Flask(__name__)

app.config.update(dict(
    DATABASE=os.path.join(CURRPATH, 'urls.db'),
    DEBUG=True,
))
app.config.from_envvar("SHURL_SETTINGS", silent=True)


class URLForm(Form):
    slug = StringField("slug", [validators.Length(min=2)])
    url = StringField("URL", [validators.Length(min=2)])

    def validate_slug(form, field):
        validchars = string.ascii_letters + string.digits + "_-"
        for char in field.data:
            if char not in validchars:
                raise validators.ValidationError("slug can contain only alphanumeric characters and _ and -")

        if slug_exists(field.data):
            raise validators.ValidationError("a slug with this name already exists")

        existing_urls = [rule.rule[1:].split("/")[0] for rule in app.url_map._rules]
        if field.data in existing_urls:
            raise validators.ValidationError("this slug is reserved for internal use")

    def validate_url(form, field):
        url = field.data
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "http://" + url
        errmsg = url + " is not a valid url"
        try:
            # let urllib2 validate the URL for us
            urllib2.urlopen(url, timeout=5)
        except urllib2.HTTPError:
            # http errors include things like a 404/403/...
            # just accept them and do not complain
            pass
        except urllib2.URLError:
            raise validators.ValidationError(errmsg)


def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv


def init_db():
    """Creates the database tables."""
    with app.app_context():
        db = get_db()
        items = db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()
        if items[0] == 0:
            # recreate the db only if empty
            with app.open_resource(os.path.join(CURRPATH, 'schema.sql'), mode='r') as f:
                db.cursor().executescript(f.read())
            db.commit()


def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db


@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


@app.route("/", methods=["GET", "POST"])
def index():
    db = get_db()

    form = URLForm(request.form)
    if request.method == "POST":
        if form.validate():
            url = form.url.data
            slug = form.slug.data
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "http://" + url

            db.execute("INSERT INTO entries (slug, url) VALUES (?, ?)", (slug, url))
            db.commit()

            form.url.data = None
            form.slug.data = None

    cur = db.execute("SELECT slug, url, click_count, timestamp FROM entries ORDER BY timestamp DESC LIMIT 10")
    entries = cur.fetchall()

    return render_template("index.html",
                           base_url=request.host,
                           entries=entries,
                           form=form)

@app.route("/top/", defaults={"limit": 10})
@app.route("/top/<int:limit>/")
def top(limit):
    db = get_db()
    cur = db.execute(
        "SELECT slug, url, click_count FROM entries ORDER BY click_count DESC, timestamp ASC LIMIT ?", [limit])
    entries = cur.fetchall()
    return render_template("top.html", limit=limit, entries=entries)


@app.route("/all")
def all_entries():
    db = get_db()
    cur = db.execute("SELECT slug, url, timestamp, click_count FROM entries ORDER BY slug DESC")
    entries = cur.fetchall()
    return render_template("all.html", entries=entries)


@app.route("/search")
def search():
    db = get_db()
    query = request.args.get("q")
    cur = db.execute(
        "SELECT slug, url, click_count FROM entries WHERE slug LIKE ? OR url LIKE ? ORDER BY click_count DESC",
        ["%%%s%%" % query, "%%%s%%" % query]
    )
    entries = cur.fetchall()
    return render_template("search.html",
                           query=query,
                           entries=entries)


@app.route("/edit/<path:slug>")
def edit(slug):
    if not slug_exists(slug):
        abort(404)

    db = get_db()
    entry = db.execute("SELECT slug, url FROM entries WHERE slug = ?", [slug]).fetchone()

    form = URLForm(request.form, slug=entry[0], url=entry[1])
    if request.method == "POST" and form.validate():
        url = form.url.data
        slug = form.slug.data
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "http://" + url

        db.execute("UPDATE entries SET slug=?, url=? WHERE slug=?", (slug, url, slug))
        db.commit()
        return redirect("index")

    return render_template("edit.html", form=form)


@app.route("/delete/<path:slug>")
def delete(slug):
    db = get_db()
    db.execute("DELETE FROM entries WHERE slug = ?", [slug])
    db.commit()
    return redirect(url_for("index"))


@app.route("/<path:slug>")
def redir(slug):
    """Catch everything else"""
    db = get_db()
    cur = db.execute("SELECT url FROM entries WHERE slug = ?", [slug])
    results = cur.fetchall()
    if not results or len(results) != 1:
        return redirect(url_for("search", q=slug))
    db.execute("UPDATE entries SET click_count = click_count + 1 WHERE slug = ?", [slug])
    db.commit()
    url = results[0][0]
    return redirect(url)


@app.route("/api/generate/")
def api_generate():
    try:
        url = request.args["url"]
    except KeyError:
        abort(400)
        return
    if not (url.startswith("http://") or url.startswith("https://")):
        abort(400)
    return jsonify({
        "slug": generate_for(url)
    })


@app.route("/api/exists/<path:slug>/")
def api_exists(slug):
    return jsonify({
        "exists": slug_exists(slug)
    })


def slug_exists(slug):
    db = get_db()
    cur = db.execute("SELECT url FROM entries WHERE slug = ?", [slug])
    results = cur.fetchall()
    return bool(results)


MAX_URL_BUCKETS = 999999999
def generate_for(url):
    # use quadratic probing for finding an empty hash bucket
    # which in our case is an unused shortened hash

    # use CRC32 as string hash
    h = binascii.crc32(url)

    # convert the hash to base 62
    base = 1
    slug = base62((h + base) % MAX_URL_BUCKETS)
    while slug_exists(slug):
        base += 1
        base = math.pow(base, 2)
        slug = base62((h + base) % MAX_URL_BUCKETS)
    return slug


def base62(num):
    numerals = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return ((num == 0) and numerals[0]) or (base62(num // 62)).lstrip(numerals[0]) + numerals[num % 62]


if __name__ == '__main__':
    init_db()
    app.run()