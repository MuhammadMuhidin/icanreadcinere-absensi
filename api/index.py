from flask import Flask, render_template, request, redirect, flash, session, Response
from math import radians, cos, sin, sqrt, atan2
from pywebpush import webpush, WebPushException
from collections import defaultdict
from datetime import datetime, time
from io import StringIO
import os, requests, csv, pytz, json, boto3

# =====================
# Flask App
# =====================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "change-me")

# =====================
# ENV & CONSTANT
# =====================
GAS_URL = 'https://script.google.com/macros/s/AKfycby3q46el12n-cENbDxoed6o8qjftkVUa_pg5seEEYXjK2riDnASilrWIZ6NLS8YDJG99w/exec'
POINTOFFICE = (-6.323856,106.784517)

USERS = {
    "Hanny":{"password":"1918","title":"Ms"},
    "Dini":{"password":"2651","title":"Ms"},
    "Mita":{"password":"0000","title":"Ms"},
    "Fiya":{"password":"8997","title":"Ms"},
    "Nadhira":{"password":"3544","title":"Ms"},
    "Lintang":{"password":"0921","title":"Mr"},
    "Noel":{"password":"1301","title":"Mr"},
}

API_KEY_BLAST = os.environ.get("BLAST_KEY", "blast321")

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY")

# =====================
# R2 CONFIG
# =====================
r2 = boto3.client(
    "s3",
    endpoint_url=os.environ["R2_ENDPOINT"],
    aws_access_key_id=os.environ["R2_ACCESS_KEY"],
    aws_secret_access_key=os.environ["R2_SECRET_KEY"]
)
R2_BUCKET = os.environ["R2_BUCKET"]

# =====================
# UTILITIES
# =====================
def r2_read_text(key):
    try:
        obj = r2.get_object(Bucket=R2_BUCKET, Key=key)
        return obj["Body"].read().decode("utf-8")
    except Exception:
        return ""

def r2_write_text(key, content, content_type="text/plain"):
    r2.put_object(
        Bucket=R2_BUCKET,
        Key=key,
        Body=content.encode("utf-8"),
        ContentType=content_type
    )

def jarak_meter(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1-a))

# =====================
# DATA FUNCTIONS (R2)
# =====================
def get_news():
    content = r2_read_text("content/news.txt").strip()
    return content if content else "Welcome to Attendance System"

def get_sisa_cuti(userid):
    data = r2_read_text("data/cuti.csv")
    if not data:
        return "leave file not found"
    for nama, sisa in csv.reader(data.splitlines()):
        if nama.lower() == userid.lower():
            return sisa
    return "no leave balance, contact your supervisor"

def load_log():
    data = r2_read_text("data/log_absen.csv")
    return list(csv.DictReader(data.splitlines())) if data else []

def save_log(rows):
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=["nama","aksi","tanggal","waktu"])
    writer.writeheader()
    writer.writerows(rows)
    r2_write_text("data/log_absen.csv", buf.getvalue(), "text/csv")

def sudah_absen_hari_ini(nama, aksi):
    today = datetime.now(pytz.timezone("Asia/Jakarta")).strftime("%Y-%m-%d")
    for r in load_log():
        if r["nama"] == nama and r["aksi"] == aksi and r["tanggal"] == today:
            return True
    return False

def simpan_log_absen(nama, aksi):
    now = datetime.now(pytz.timezone("Asia/Jakarta"))
    rows = load_log()
    rows.append({
        "nama": nama,
        "aksi": aksi,
        "tanggal": now.strftime("%Y-%m-%d"),
        "waktu": now.strftime("%H:%M:%S")
    })
    save_log(rows)

def get_latest_absen_for_user(username):
    rows = [r for r in load_log() if r["nama"].lower() == username.lower()]
    if not rows:
        return None, None, None

    grouped = defaultdict(list)
    for r in rows:
        grouped[r["tanggal"]].append(r)

    latest_date = max(grouped.keys())
    checkin = checkout = None
    for r in grouped[latest_date]:
        if r["aksi"].lower() == "check in":
            checkin = r["waktu"]
        elif r["aksi"].lower() == "check out":
            checkout = r["waktu"]

    return latest_date, checkin, checkout

# =====================
# ROUTES
# =====================
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        userid = request.form.get("userid")
        pw = request.form.get("password")
        if userid in USERS and USERS[userid]["password"] == pw:
            session["userid"] = userid
            session["title"] = USERS[userid]["title"]
            return redirect("/absence")
        flash("Incorrect userid or password", "error")

    if "userid" in session:
        return redirect("/absence")
    return render_template("login.html", news=get_news())

@app.route("/absence", methods=["GET","POST"])
def absence():
    if "userid" not in session:
        return redirect("/")

    user = session["userid"]
    date, checkin, checkout = get_latest_absen_for_user(user)

    if request.method == "POST":
        aksi = request.form.get("aksi")
        lat = float(request.form.get("latitude"))
        lon = float(request.form.get("longitude"))

        if sudah_absen_hari_ini(user, aksi):
            flash("Already done today", "error")
            return redirect("/absence")

        if jarak_meter(lat, lon, *POINTOFFICE) > 150:
            flash("Too far from office", "error")
            return redirect("/absence")

        requests.post(GAS_URL, json={
            "nama": user,
            "aksi": aksi,
            "mood": request.form.get("mood"),
            "notes": request.form.get("notes")
        })

        simpan_log_absen(user, aksi)
        flash("Recorded successfully!", "success")
        return redirect("/absence")

    return render_template(
        "absence.html",
        nama=user,
        title=session["title"],
        date=date,
        checkin=checkin,
        checkout=checkout,
        news=get_news(),
        sisa=get_sisa_cuti(user)
    )

@app.route("/change_photo", methods=["POST"])
def change_photo():
    if "userid" not in session:
        return Response(status=401)

    file = request.files.get("file")
    if not file:
        return Response(status=400)

    r2.put_object(
        Bucket=R2_BUCKET,
        Key=f"profiles/{session['userid']}.jpg",
        Body=file.read(),
        ContentType="image/jpeg"
    )
    return Response(status=200)

# =====================
# ENTRYPOINT FOR VERCEL
# =====================
app = app
