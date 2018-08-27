import twitter
import json
import configparser
from flask import Flask, render_template, request, redirect, url_for, flash, Markup
app = Flask(__name__)

config = configparser.ConfigParser()
config.read("config.ini")
app.secret_key = config["flask"].get('secret_key')

api = twitter.Api(consumer_key=config["twitter"].get("consumer_key"),
                  consumer_secret=config["twitter"].get("consumer_secret"),
                  access_token_key=config["twitter"].get("access_token_key"),
                  access_token_secret=config["twitter"].get("access_token_secret"),
                  cache=None,
                  sleep_on_rate_limit=True,
                  tweet_mode="extended")

print(api.VerifyCredentials())

@app.route("/")
def hello():
    return "Hello World!"

@app.route("/timeline")
def timeline():
    try:
        tl = api.GetHomeTimeline()
        for t in tl:
            t = htmlize_tweet(t)
    except twitter.error.TwitterError as e:
        flash("Une erreur est survenue: {}".format(e.message))
        return redirect(url_for("lists"))
    return render_template("tweet_list.html", tweets=tl)

@app.route("/user")
def user_summary():
    _id = request.args.get("id", None, type=int)
    try:
        user = api.GetUser(user_id=_id)
        user.profile_image_url_https = user.profile_image_url_https.replace('normal', '200x200')
        tl = api.GetUserTimeline(user_id=_id)
        for t in tl:
            t = htmlize_tweet(t)
    except twitter.error.TwitterError as e:
        flash("Une erreur est survenue: {}".format(e.message))
        return redirect(url_for("lists"))
    return render_template("user_summary.html", user=user, tweets=tl)


@app.route("/list/timeline")
def list_timeline():
    _id = request.args.get("id", type=int)
    try:
        tl = api.GetListTimeline(list_id=_id)
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

@app.route("/lists")
def lists():
    return render_template("lists.html", lists=api.GetLists())

@app.route("/list/members")
def list_members():
    _id = request.args.get("id", type=int)
    try:
        members = api.GetListMembers(list_id=_id, skip_status=False)
        members = sort_userlist(members)
        for m in members:
            m.profile_image_url_https = m.profile_image_url_https.replace('normal', '200x200')
    except twitter.error.TwitterError as e:
        flash("Une erreur est survenue: {}".format(e.message))
        return redirect(url_for("lists"))
    return render_userlist(members)

@app.route("/followers")
def list_followers():
    return list_generic(request, api.GetFollowers)

@app.route("/following")
def list_following():
    return list_generic(request, api.GetFriends)

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

#tl = api.GetHomeTimeline()
#for status in tl:
#    print("{}:\t{}\n\n".format(status.user.name, status.full_text))
"""
print(api.GetLists())

tl = api.GetListTimeline(list_id=1006990616050454529)
for status in tl:
    print("{}: {}".format(status.user.name, status.full_text))
"""
app.run(debug=True, use_debugger=True, use_reloader=True)
