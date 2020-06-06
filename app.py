import twitter
import json
import configparser
import os
from functools import wraps
from requests_oauthlib import OAuth1Session, oauth1_session
from flask import Flask, render_template, request, redirect, url_for, flash, Markup, session, abort
app = Flask(__name__)

def init_config(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)
    def get_config(key, val):
        ev = "{}_{}".format(key, val)
        return os.environ[ev] if ev in os.environ else config[key].get(val)
    return get_config

get_config = init_config("config.ini")

app.secret_key = get_config("flask", "secret_key")

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('oauth_token', '') == '':
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

def make_api():
    return twitter.Api(consumer_key=get_config("twitter", "consumer_key"),
                  consumer_secret=get_config("twitter", "consumer_secret"),
                  access_token_key=session['oauth_token'],
                  access_token_secret=session['oauth_token_secret'],
                  cache=None,
                  sleep_on_rate_limit=True,
                  tweet_mode="extended")

@app.route("/login", methods=['GET', 'POST'])
def login_page():
    consumer_key=get_config("twitter", "consumer_key")
    consumer_secret=get_config("twitter", "consumer_secret")
    verifier = request.args.get("oauth_verifier", "")
    if request.method == "GET" and verifier == "": # Etape 1: récuperer le secret et demander le verifier
        fancy_redirect = True
        try: # Tentative de connection avec redirection. PIN si echec
            oauth_client = OAuth1Session(consumer_key, client_secret=consumer_secret,
                                     callback_uri=url_for("login_page", _external=True))
            resp = oauth_client.fetch_request_token("https://api.twitter.com/oauth/request_token")
        except oauth1_session.TokenRequestDenied as e:
            fancy_redirect = False
            oauth_client = OAuth1Session(consumer_key, client_secret=consumer_secret,
                                     callback_uri="oob")
            resp = oauth_client.fetch_request_token("https://api.twitter.com/oauth/request_token")
        url = oauth_client.authorization_url("https://api.twitter.com/oauth/authorize")
        session['temp_oauth_token'] = resp.get('oauth_token') # Stockage des secrets pour l'étape 2
        session['temp_oauth_token_secret'] = resp.get('oauth_token_secret')
        return redirect(url) if fancy_redirect else render_template('login.html', url=url)
    else: # Etape 2: recuperer le verifier et demander les token de connection
        if verifier != "":
            pincode = verifier
        else:
            pincode = request.form['pin']
        oauth_client = OAuth1Session(consumer_key, client_secret=consumer_secret,
                                     resource_owner_key=session['temp_oauth_token'],
                                     resource_owner_secret=session['temp_oauth_token_secret'],
                                     verifier=pincode)
        del session['temp_oauth_token']
        del session['temp_oauth_token_secret']
        resp = oauth_client.fetch_access_token("https://api.twitter.com/oauth/access_token")
        session['oauth_token'] = resp.get('oauth_token')
        session['oauth_token_secret'] = resp.get('oauth_token_secret')
        return redirect('home')


@app.route("/logout")
def logout():
    session.clear()
    return redirect('home')

@app.route("/")
@app.route("/home")
def home():
    return render_template("home.html")

@app.route("/timeline")
@requires_auth
def timeline():
    _last_tweet = request.args.get('last_tweet', None, type=int)
    try:
        tl = make_api().GetHomeTimeline(count=200, max_id=_last_tweet)
        for t in tl:
            t = htmlize_tweet(t)
    except twitter.error.TwitterError as e:
        flash("Une erreur est survenue: {}".format(e.message))
        return redirect(url_for("lists"))
    return render_template("tweet_list.html", tweets=tl)

@app.route("/user")
@requires_auth
def user_summary():
    _id = request.args.get("id", None, type=int)
    _last_tweet = request.args.get('last_tweet', None, type=int)
    try:
        user = make_api().GetUser(user_id=_id)
        user.profile_image_url_https = user.profile_image_url_https.replace('normal', '200x200')
        tl = make_api().GetUserTimeline(user_id=_id, count=200, max_id=_last_tweet)
        for t in tl:
            t = htmlize_tweet(t)
    except twitter.error.TwitterError as e:
        flash("Une erreur est survenue: {}".format(e.message))
        return redirect(url_for("lists"))
    return render_template("user_summary.html", user=user, tweets=tl)

@app.route("/user/favorites")
@requires_auth
def user_favorites():
    _id = request.args.get("id", None, type=int)
    _last_tweet = request.args.get('last_tweet', None, type=int)
    try:
        user = make_api().GetUser(user_id=_id)
        user.profile_image_url_https = user.profile_image_url_https.replace('normal', '200x200')
        tl = make_api().GetFavorites(user_id=_id, count=200, max_id=_last_tweet)
        for t in tl:
            t = htmlize_tweet(t)
    except twitter.error.TwitterError as e:
        flash("Une erreur est survenue: {}".format(e.message))
        return redirect(url_for("lists"))
    return render_template("user_summary.html", user=user, tweets=tl)

@app.route("/list/timeline")
@requires_auth
def list_timeline():
    _id = request.args.get("id", type=int)
    _last_tweet = request.args.get('last_tweet', None, type=int)
    try:
        tl = make_api().GetListTimeline(list_id=_id, count=200, max_id=_last_tweet)
        for t in tl:
            t = htmlize_tweet(t)
    except twitter.error.TwitterError as e:
        flash("Une erreur est survenue: {}".format(e.message))
        return redirect(url_for("lists"))
    return render_template("tweet_list.html", tweets=tl)

def htmlize_tweet(t):
    if t.retweeted_status:
        t.full_text = t.retweeted_status.full_text
        t.urls = t.retweeted_status.urls
        t.user_mentions = t.retweeted_status.user_mentions
        t.hashtags = t.retweeted_status.hashtags
        if t.retweeted_status.media:
            t.media = t.retweeted_status.media
    t.full_text = t.full_text.replace("\n", "<br />")
    for url in t.urls:
        t.full_text = t.full_text.replace(url.url, "<a href=\"{}\" class=\"tweet_link\">{}</a>".format(url.expanded_url, url.url))
    for u in t.user_mentions:
        t.full_text = t.full_text.replace("@{}".format(u.screen_name), "<a href=\"#\" class=\"tweet_mention\">@{}</a>".format(u.screen_name))
    for h in t.hashtags:
        t.full_text = t.full_text.replace("#{}".format(h.text), "<a href=\"#\" class=\"tweet_hashtag\">#{}</a>".format(h.text))
    if t.media:
        for med in t.media:
            t.full_text = t.full_text.replace(med.url, "")
    t.full_text = Markup(t.full_text)
    return t

@app.route("/tweet/response")
@requires_auth
def tweet_info_response():
    _id = request.args.get("id", type=int)
    if _id:
        try:
            api = make_api()
            tweet = api.GetStatus(_id)
            rep = list(get_replies(api, tweet))
            prev = get_replied_tweets(api, tweet)
        except twitter.error.TwitterError as e:
            flash("Une erreur est survenue: {}".format(e.message))
            return redirect(url_for("home"))
#        for r in rep:
#           r = htmlize_tweet(r)
        return render_template("tweet_replies.html", tweet_initial=tweet, tweets=rep, prev=prev)

def get_replied_tweets(api, tweet):
    ret = list()
    _id = tweet.in_reply_to_status_id
    while _id != None:
        tw = api.GetStatus(_id)
        ret.append(tw)
        _id = tw.in_reply_to_status_id
    return ret.reverse()

def get_replies(api, tweet, max_id=None): # source : https://gist.github.com/edsu/54e6f7d63df3866a87a15aed17b51eaf
    user = tweet.user.screen_name
    tweet_id = tweet.id
    while True:
        q = "to:{}".format(user)
        try:
            replies = api.GetSearch(term=q, since_id=tweet_id, max_id=max_id, count=200)
        except twitter.error.TwitterError as e:
            flash("Une erreur est survenue: {}".format(e.message))
        for reply in replies:
            if reply.in_reply_to_status_id == tweet_id:
                rep = [reply]
                rep2 = []
                for reply_to_reply in get_replies(api, reply):
                    rep2.append(reply_to_reply)
                if len(rep2) != 0:
                    rep.append(rep2)
                yield rep
            max_id = reply.id
        if len(replies) != 200:
            break

@app.route('/search', methods=["GET"])
@requires_auth
def search():
    q = request.args.get("query", type=str)
    _last_tweet = request.args.get('last_tweet', None, type=int)
    if q:
        results = make_api().GetSearch(term=q, count=20, max_id=_last_tweet, result_type="recent")
        for t in results:
            t = htmlize_tweet(t)
        return render_template("tweet_list.html", tweets=results, search_query=q)
    else:
        abort(400)


@app.route("/lists")
@requires_auth
def lists():
    return render_template("lists.html", lists=make_api().GetLists())

@app.route("/list/members")
@requires_auth
def list_members():
    _id = request.args.get("id", type=int)
    try:
        members = make_api().GetListMembers(list_id=_id, skip_status=False)
        members = sort_userlist(members)
        for m in members:
            m.profile_image_url_https = m.profile_image_url_https.replace('normal', '200x200')
    except twitter.error.TwitterError as e:
        flash("Une erreur est survenue: {}".format(e.message))
        return redirect(url_for("lists"))
    return render_userlist(members)

@app.route("/followers")
@requires_auth
def list_followers():
    return list_generic(request, make_api().GetFollowers)

@app.route("/following")
@requires_auth
def list_following():
    return list_generic(request, make_api().GetFriends)

def list_generic(request, endpoint):
    _id = request.args.get("id", None, type=int)
    try:
        members = endpoint(user_id=_id, skip_status=False)
        members = sort_userlist(members)
        for m in members:
            m.profile_image_url_https = m.profile_image_url_https.replace('normal', '200x200')
    except twitter.error.TwitterError as e:
        flash("Une erreur est survenue: {}".format(e.message))
        return redirect(url_for("lists")) #TODO: 
    return render_userlist(members)

def render_userlist(user_list):
    return render_template("list_member.html", members=user_list)

def sort_userlist(user_list):
    return sorted(user_list, key=lambda x: x.status.created_at_in_seconds if x.status else 0, reverse=True)

if __name__ == "__main__":
    app.run(debug=True, use_debugger=True, use_reloader=True)
