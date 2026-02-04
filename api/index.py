from flask import Flask, render_template, request, redirect, flash, session, Response
from math import radians, cos, sin, sqrt, atan2
from collections import defaultdict
from supabase import create_client
from datetime import datetime
from io import StringIO
import os, requests, csv, pytz, json, boto3

# =====================
# Flask App
# =====================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")

# =====================
# CONSTANT
# =====================
GAS_URL = os.environ.get("GAS_URL")
POINTOFFICE = (-6.323856, 106.784517)

USERS = {
    "Hanny": {"password": "1918", "title": "Ms"},
    "Dini": {"password": "2651", "title": "Ms"},
    "Mita": {"password": "0000", "title": "Ms"},
    "Fiya": {"password": "8997", "title": "Ms"},
    "Nadhira": {"password": "3544", "title": "Ms"},
    "Lintang": {"password": "0921", "title": "Mr"},
    "Noel": {"password": "1301", "title": "Mr"},
}

TZ = pytz.timezone("Asia/Jakarta")

# =====================
# SUPABASE (LAZY INIT)
# =====================
_sb = None

def get_supabase():
     global _sb
     if _sb is None:
         url = os.environ.get("SUPABASE_URL")
         key = os.environ.get("SUPABASE_ROLE_KEY")
         if not url or not key:
             raise RuntimeError("Supabase credentials not set")
         _sb = create_client(url, key)
     return _sb

# =====================
# R2 (LAZY INIT)
# =====================
_r2 = None

def get_r2():
    global _r2
    if _r2 is None:
        endpoint = os.environ.get("R2_ENDPOINT")
        key = os.environ.get("R2_KEY")
        secret = os.environ.get("R2_SECRET")

        if not endpoint or not key or not secret:
            raise RuntimeError("R2 credentials not set")

        _r2 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=key,
            aws_secret_access_key=secret,
        )
    return _r2

R2_BUCKET = os.environ.get("R2_BUCKET")

# =====================
# R2 HELPERS
# =====================
def r2_read_text(key):
    try:
        r2 = get_r2()
        obj = r2.get_object(Bucket=R2_BUCKET, Key=key)
        return obj["Body"].read().decode("utf-8")
    except Exception:
        return ""

def r2_write_text(key, content, content_type="text/plain"):
    r2 = get_r2()
    r2.put_object(
        Bucket=R2_BUCKET,
        Key=key,
        Body=content.encode("utf-8"),
        ContentType=content_type
    )

# =====================
# UTILITIES
# =====================
def jarak_meter(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))

# =====================
# DATA FUNCTIONS
# =====================
def check_late(checkin_time):
    if isinstance(checkin_time, str):
        checkin_time = datetime.strptime(checkin_time, "%H:%M:%S").time()

    tz = pytz.timezone("Asia/Jakarta")
    today = datetime.now(tz).date()
    hari_ini = today.weekday()

    if hari_ini == 5:  # 0=Senin, 1=Selasa, 2=Rabu, 3=Kamis, 4=Jumat, 5=Sabtu, 6=Minggu
        batas_telat = datetime.strptime("09:00:00", "%H:%M:%S").time()
    else:
        batas_telat = datetime.strptime("10:10:00", "%H:%M:%S").time()

    if checkin_time > batas_telat:
        late_time = datetime.combine(today, checkin_time) - datetime.combine(today, batas_telat)

        hh = late_time.seconds // 3600
        mm = (late_time.seconds % 3600) // 60
        ss = late_time.seconds % 60
        return f"{hh:02}:{mm:02}:{ss:02}"

    return "On time!"

def get_news():
    try:
        sb = get_supabase()
        res = (
            sb.table("news")
            .select("content")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]["content"]
    except Exception:
        pass
    return "Welcome to Attendance System"

def get_sisa_cuti(userid):
    data = r2_read_text("data/cuti.csv")
    if not data:
        return "leave file not found"

    for nama, sisa in csv.reader(data.splitlines()):
        if nama.lower() == userid.lower():
            return sisa

    return "no leave balance, contact your supervisor"

def load_log():
    try:
        sb = get_supabase()
        res = sb.table("log_absen").select("*").execute()
        return res.data or []
    except Exception:
        return []

def save_log(rows):
    pass

def sudah_absen_hari_ini(nama, aksi):
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    sb = get_supabase()
    res = (
        sb.table("log_absen")
        .select("id")
        .eq("nama", nama)
        .eq("aksi", aksi)
        .eq("tanggal", today)
        .limit(1)
        .execute()
    )
    return bool(res.data)

def simpan_log_absen(nama, aksi):
    sb = get_supabase()
    sb.table("log_absen").insert({
        "nama": nama,
        "aksi": aksi,
        "tanggal": now.strftime("%Y-%m-%d"),
        "waktu": now.strftime("%H:%M:%S"),
    }).execute()

def get_latest_absen_for_user(username):
    sb = get_supabase()
    res = (
        sb.table("log_absen")
        .select("tanggal, aksi, waktu")
        .eq("nama", username)
        .order("tanggal", desc=True)
        .order("waktu", desc=True)
        .execute()
    )

    if not res.data:
        return None, None, None

    latest_date = res.data[0]["tanggal"]
    checkin = checkout = None

    for r in res.data:
        if r["tanggal"] != latest_date:
            break
        if r["aksi"].lower() == "check in":
            checkin = r["waktu"]
        elif r["aksi"].lower() == "check out":
            checkout = r["waktu"]

    return latest_date, checkin, checkout

# =====================
# ROUTES
# =====================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        userid = request.form.get("userid")
        pw = request.form.get("password")

        if userid in USERS and USERS[userid]["password"] == pw:
            session.permanent = True
            session["userid"] = userid
            session["title"] = USERS[userid]["title"]
            return redirect("/absence")

        flash("Incorrect userid or password", "error")

    if "userid" in session:
        return redirect("/absence")

    return render_template("login.html", news=get_news())

@app.after_request
def add_no_cache_headers(response):
    if request.endpoint == 'login':
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

@app.route("/absence", methods=["GET", "POST"])
def absence():
    if "userid" not in session:
        return redirect("/")

    user = session["userid"]
    date, checkin, checkout = get_latest_absen_for_user(user)
    late_status = ''

    if request.method == "POST":
        aksi = request.form.get("aksi")

        try:
            lat = float(request.form.get("latitude", "0"))
            lon = float(request.form.get("longitude", "0"))
        except ValueError:
            flash("Invalid GPS", "error")
            return redirect("/absence")

        if sudah_absen_hari_ini(user, aksi):
            flash("Already done today", "error")
            return redirect("/absence")

        if jarak_meter(lat, lon, *POINTOFFICE) > 150:
            flash("Too far from office", "error")
            return redirect("/absence")

        if aksi.lower() == "check in":
            now = datetime.now(pytz.timezone("Asia/Jakarta")).time()
            late_status = check_late(now)

        try:
            requests.post(GAS_URL, json={
                "nama": user,
                "aksi": aksi,
                "late_status": late_status,
                "mood": request.form.get("mood"),
                "notes": request.form.get("notes")
            }, timeout=5)
        except Exception:
            pass

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

    r2 = get_r2()
    r2.put_object(
        Bucket=R2_BUCKET,
        Key=f"profiles/{session['userid']}.jpg",
        Body=file.read(),
        ContentType="image/jpeg"
    )
    return Response(status=200)

@app.route("/upload", methods=["GET", "POST"])
def upload():
    # hanya admin tertentu
    if session.get("userid") not in ["Mita", "Hanny"]:
        return redirect("/")

    if request.method == "POST":
        file = request.files.get("file")
        password = request.form.get("password")
        jenis = request.form.get("jenis")

        if password != "nbpwd31":
            flash("Wrong password!", "error")
            return redirect("/upload")

        if not file or jenis not in ["banner", "cuti"]:
            flash("Invalid upload type!", "error")
            return redirect("/upload")

        # tentukan target R2 key
        if jenis == "banner":
            if not file.filename.endswith(".txt"):
                flash("Banner must be .txt file", "error")
                return redirect("/upload")
            r2_key = "content/news.txt"
            content_type = "text/plain"

        elif jenis == "cuti":
            if session.get("userid") != "Hanny":
                flash("You are not allowed to upload leave files!", "error")
                return redirect("/upload")
            if not file.filename.endswith(".csv"):
                flash("Cuti must be .csv file", "error")
                return redirect("/upload")
            r2_key = "data/cuti.csv"
            content_type = "text/csv"

        try:
            r2 = get_r2()
            r2.put_object(
                Bucket=R2_BUCKET,
                Key=r2_key,
                Body=file.read(),
                ContentType=content_type
            )
            flash(f"Upload {jenis.upper()} success!", "success")

        except Exception as e:
            flash("Upload failed!", "error")

        return redirect("/upload")

    return render_template("upload.html")

@app.route("/__r2_test")
def r2_test():
    try:
        r2 = get_r2()
        r2.head_bucket(Bucket=R2_BUCKET)
        return "R2 CONNECTED", 200
    except Exception as e:
        return f"R2 ERROR: {str(e)}", 500

@app.route("/__sp_test")
def sp_test():
    try:
        sb = get_supabase()

        res = (
            sb.table("news")
            .select("*")
            .execute()
        )

        if not res.data:
            return "SUPABASE CONNECTED, NEWS EMPTY", 200

        return f"SUPABASE CONNECTED, NEWS: {res.data[0]['content']}", 200

    except Exception as e:
        return f"SUPABASE ERROR: {str(e)}", 500