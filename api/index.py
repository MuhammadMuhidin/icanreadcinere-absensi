from flask import Flask, render_template, request, redirect, jsonify, flash, session, Response
from math import radians, cos, sin, sqrt, atan2
from collections import defaultdict
from supabase import create_client
from io import StringIO
import os, requests, csv, pytz, json, boto3
from datetime import datetime, date, timedelta
from dateutil.parser import isoparse

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

def load_users():
    raw = os.environ.get("USERS_JSON")
    if not raw:
        raise RuntimeError("USERS_JSON env not set")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError("USERS_JSON is invalid JSON")
USERS = load_users()

def send_wa(phone, message):
    token = os.environ.get("FTICR_TOKEN")
    if not token or not phone:
        return
    try:
        requests.post(
            "https://api.fonnte.com/send",
            headers={
                "Authorization": token
            },
            data={
                "target": phone,
                "message": message,
                "delay": 2
            },
            timeout=10
        )
    except Exception as e:
        print("FONNTE ERROR:", e)

# =====================
# CONSTANT
# =====================
GAS_URL = os.environ.get("GAS_URL")
POINTOFFICE = list(map(float, os.getenv("POINTOFFICE").split(",")))
R2_PUBLIC_BASE_URL = os.getenv("R2_PUBLIC_BASE_URL")
TZ = pytz.timezone("Asia/Jakarta")

# =====================
# HELPER PREFIX TABLE
# =====================
DB_PREFIX = os.getenv("DB_PREFIX", "")
def T(name: str) -> str:
    return f"{name}{DB_PREFIX}"

# =====================
# HELPER CONFLICT TABLE
# =====================
NON_TEACHERS = {"Hanny", "Dini", "Lintang"}

def is_non_teacher(name: str) -> bool:
    return name in NON_TEACHERS

def non_teacher_sql_tuple() -> str:
    return "(" + ",".join(f'"{n}"' for n in NON_TEACHERS) + ")"

def has_leave_conflict(sb, leave_date_raw: str, exclude_id: int | None = None) -> dict | None:
    """
    Cek conflict antar TEACHER saja.
    Non-teacher otomatis diabaikan.
    """
    q = (
        sb.table(T("paid_leave"))
        .select("id, name, leave_date")
        .eq("leave_date", leave_date_raw)
        .in_("status", ["WAITING APPROVAL", "APPROVED"])
        .filter("name", "not.in", non_teacher_sql_tuple())
    )

    if exclude_id is not None:
        q = q.neq("id", exclude_id)

    res = q.execute()
    return res.data[0] if res.data else None

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
        today = date.today().isoformat()
        
        res = (
            sb.table(T("news"))
            .select("content")
            .lte("published_at", today)
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
    try:
        sb = get_supabase()
        res = (
            sb.table(T("balance"))
            .select("sisa")
            .eq("nama", userid)
            .limit(1)
            .execute()
        )

        if res.data:
            return int(res.data[0]["sisa"])
            
        return None

    except Exception as e:
        print("GET CUTI ERROR:", e)

    return None

def load_log():
    try:
        sb = get_supabase()
        res = sb.table(T("log_absen")).select("*").execute()
        return res.data or []
    except Exception:
        return []

def sudah_absen_hari_ini(nama, aksi):
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    sb = get_supabase()
    res = (
        sb.table(T("log_absen"))
        .select("id")
        .eq("nama", nama)
        .eq("aksi", aksi)
        .eq("tanggal", today)
        .limit(1)
        .execute()
    )
    return bool(res.data)

def simpan_log_absen(nama, aksi):
    now = datetime.now(TZ)
    sb = get_supabase()
    sb.table(T("log_absen")).insert({
        "nama": nama,
        "aksi": aksi,
        "tanggal": now.strftime("%Y-%m-%d"),
        "waktu": now.strftime("%H:%M:%S"),
    }).execute()

def get_latest_absen_for_user(username):
    sb = get_supabase()
    res = (
        sb.table(T("log_absen"))
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
        
        if jarak_meter(lat, lon, POINTOFFICE[0], POINTOFFICE[1]) > 150:
            flash("Too far from office", "error")
            return redirect("/absence")

        if aksi.lower() == "check in":
            now = datetime.now(pytz.timezone("Asia/Jakarta")).time()
            late_status = check_late(now)

        try:
            requests.post(
                GAS_URL,
                json={
                    "nama": user,
                    "aksi": aksi,
                    "late_status": late_status,
                    "mood": request.form.get("mood"),
                    "notes": request.form.get("notes"),
                },
                timeout=5,
            )
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
        sisa=get_sisa_cuti(user),
        R2_PUBLIC_BASE_URL=R2_PUBLIC_BASE_URL
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
    if session.get("userid") not in ["Mita", "Hanny"]:
        return redirect("/")

    sb = get_supabase()

    if request.method == "POST":
        password = request.form.get("password")
        jenis = request.form.get("jenis")

        if password != "nbpwd31":
            flash("Wrong password!", "error")
            return redirect("/upload")

        try:
            # === BANNER / NEWS ===
            if jenis == "banner":
                content = request.form.get("content", "").strip()
                publish_mode = request.form.get("publish_mode", "now")
                if not content:
                    flash("Content cannot be empty", "error")
                    return redirect("/upload")

                today = date.today()
            
                if publish_mode == "schedule":
                    published_at = request.form.get("published_at")
                    if not published_at:
                        flash("Publish date is required for schedule", "error")
                        return redirect("/upload")
            
                    schedule_date = date.fromisoformat(published_at)
            
                    if schedule_date < today:
                        flash("Scheduled date must be today or later", "error")
                        return redirect("/upload")
            
                    published_at = schedule_date.isoformat()
            
                else:
                    # publish now → tanggal hari ini
                    published_at = today.isoformat()
            
                sb.table(T("news")).insert({
                    "content": content,
                    "published_at": published_at
                }).execute()

                flash("News updated successfully", "success")

            # === CUTI ===
            elif jenis == "cuti":
                if session.get("userid") != "Hanny":
                    flash("You are not allowed", "error")
                    return redirect("/upload")

                nama = request.form.get("userid")
                sisa = request.form.get("sisa")

                if not nama or sisa is None:
                    flash("Nama dan sisa wajib diisi", "error")
                    return redirect("/upload")

                res = (
                        sb.table(T("balance"))
                        .update({"sisa": sisa})
                        .eq("nama", nama)
                        .execute()
                    )
                
                if not res.data:
                    flash(f"Name '{nama}' not found!", "error")
                else:
                    flash("Leave balance updated", "success")

        except Exception as e:
            print("UPLOAD ERROR:", e)
            flash("Operation failed", "error")

        return redirect("/upload")

    today = date.today().isoformat()
    scheduled_news = (
    sb.table(T("news"))
    .select("content, published_at")
    .gt("published_at", today)
    .execute()
    ).data
    return render_template("upload.html",scheduled_news=scheduled_news)

@app.route("/__checkdb")
def checkdb():
    result = {
        "r2": None,
        "supabase": None,
    }

    # === TEST R2 ===
    try:
        r2 = get_r2()
        r2.head_bucket(Bucket=R2_BUCKET)
        result["r2"] = "CONNECTED"
    except Exception as e:
        result["r2"] = f"ERROR: {str(e)}"

    # === TEST SUPABASE ===
    try:
        sb = get_supabase()
        res = table(T("news")).select("id").limit(1).execute()

        if not res.data:
            result["supabase"] = "CONNECTED (no data)"
        else:
            result["supabase"] = "CONNECTED (with data)"
    except Exception as e:
        result["supabase"] = f"ERROR: {str(e)}"

    # === FINAL RESPONSE ===
    status_code = 200
    if "ERROR" in result["r2"] or "ERROR" in result["supabase"]:
        status_code = 500

    return result, status_code

@app.route("/paid_leave")
def paid_leave():
    if "userid" not in session:
        return redirect("/")

    return render_template(
        "paid_leave.html",
        SESSION_NAME=session["userid"]
    )
    
@app.route("/leave", methods=["GET"])
def get_leave():
    if "userid" not in session:
        return {"error": "unauthorized"}, 401

    sb = get_supabase()
    res = (
        sb.table(T("paid_leave"))
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    return {"data": res.data or []}

@app.route("/leave", methods=["POST"])
def submit_leave():
    if "userid" not in session:
        return {"error": "unauthorized"}, 401

    data = request.json
    leave_date_raw = data.get("leave_date")
    user_id = session["userid"]
    today = date.today()
    sb = get_supabase()
        
    #  Wajib ada
    if not leave_date_raw:
        return "leave_date required", 400

    #  Parse & validasi format
    try:
        leave_date = isoparse(leave_date_raw).date()
    except Exception:
        return "invalid date format", 400

    #  Tidak boleh tanggal lampau
    if leave_date < today:
        return "leave date cannot be in the past", 400

    # Batas maksimal (opsional, aman)
    if (leave_date - today).days > 30:
        return "leave date too far in the future", 400

    # 🔑 conflict hanya untuk teacher
    if not is_non_teacher(user_id):
        conflict = has_leave_conflict(sb, leave_date_raw)
        if conflict:
            return jsonify(
                message=f"Oops! {conflict['name']} already has a leave request on {conflict['leave_date']}"
            ), 409
        
    # Insert
    sb.table(T("paid_leave")).insert({
        "name": session["userid"],
        "leave_date": leave_date_raw,
        "status": "WAITING APPROVAL"
    }).execute()

    return {"message": "submitted"}, 201
    
@app.route("/leave/<int:leave_id>/cancel", methods=["PATCH"])
def cancel_leave(leave_id):
    if "userid" not in session:
        return {"error": "unauthorized"}, 401

    sb = get_supabase()
    leave = (
        sb.table(T("paid_leave"))
        .select("name, status")
        .eq("id", leave_id)
        .single()
        .execute()
    )

    if not leave.data:
        return {"error": "not found"}, 404

    if leave.data["name"] != session["userid"]:
        return {"error": "forbidden"}, 403

    if leave.data["status"] != "WAITING APPROVAL":
        return {"error": "cannot cancel"}, 400

    sb.table(T("paid_leave")) \
        .update({"status": "CANCELED"}) \
        .eq("id", leave_id) \
        .execute()

    return {"message": "canceled"}

@app.route("/leave/<int:leave_id>/decision", methods=["PATCH"])
def decision_leave(leave_id):
    if session.get("userid") != "Hanny":
        return {"error": "forbidden"}, 403

    data = request.json
    action = data.get("action")
    reason = data.get("reason", "").strip()

    if action not in ("APPROVED", "REJECTED"):
        return {"error": "invalid action"}, 400

    if action == "REJECTED" and not reason:
        return {"error": "reason required"}, 400

    sb = get_supabase()

    # 1️⃣ Ambil data leave (nama & status)
    leave = (
        sb.table(T("paid_leave"))
        .select("name, status, leave_date")
        .eq("id", leave_id)
        .single()
        .execute()
    )

    if not leave.data:
        return {"error": "not found"}, 404

    if leave.data["status"] != "WAITING APPROVAL":
        return {"error": "already processed"}, 400

    # 2️⃣ Jika APPROVE → potong sisa cuti
    # nama HARUS didefinisikan di awal
    nama = leave.data["name"]
    leave_date = leave.data["leave_date"]
    
    if action == "APPROVED":
        balance = (
            sb.table(T("balance"))
            .select("sisa")
            .eq("nama", nama)
            .single()
            .execute()
        )
    
        if not balance.data or balance.data["sisa"] <= 0:
            return {"error": "no leave balance"}, 400
    
        sb.table(T("balance")) \
            .update({"sisa": balance.data["sisa"] - 1}) \
            .eq("nama", nama) \
            .execute()
    
        sb.table(T("paid_leave")) \
            .update({"status": "APPROVED", "reason": None}) \
            .eq("id", leave_id) \
            .eq("status", "WAITING APPROVAL") \
            .execute()
    
        user_data = USERS.get(nama)
        phone = user_data.get("phone") if user_data else None
        if phone:
            send_wa(
                phone,
                f"Yay! your request for leave on {leave_date} has been approved 🎉"
            )
    
    else:  # REJECT
        sb.table(T("paid_leave")) \
            .update({"status": "REJECTED", "reason": reason}) \
            .eq("id", leave_id) \
            .eq("status", "WAITING APPROVAL") \
            .execute()
    
        user_data = USERS.get(nama)
        phone = user_data.get("phone") if user_data else None
        if phone:
            send_wa(
                phone,
                f"Hi, your request for leave on {leave_date} was rejected with reason: {reason}"
            )

    return {"message": action}

# =========================
# API: WAIT count (Hanny only)
# =========================
@app.route("/api/leave/wait-count")
def wait_count_api():
    if session.get("userid") != "Hanny":
        return {"count": 0}, 403
        
    sb = get_supabase()
    res = sb.table(T("paid_leave")) \
        .select("id", count="exact") \
        .eq("status", "WAITING APPROVAL") \
        .execute()

    return {"count": res.count or 0}, 200

@app.route("/leave/<int:id>", methods=["PATCH"])
def edit_leave(id):
    data = request.json or {}
    leave_date_raw = data.get("leave_date")
    user_id = session["userid"]

    if not leave_date_raw:
        return "leave_date required", 400

    # validasi format tanggal
    try:
        isoparse(leave_date_raw)
    except Exception:
        return "invalid date format", 400

    sb = get_supabase()

    # 🔑 conflict hanya untuk teacher
    if not is_non_teacher(user_id):
        conflict = has_leave_conflict(sb, leave_date_raw, exclude_id=id)
        if conflict:
            return (
                f"Oops! {conflict['name']} already has a leave request on {conflict['leave_date']}",
                409,
            )
        
    # update hanya jika masih WAITING
    res = sb.table(T("paid_leave")) \
        .update({"leave_date": leave_date_raw}) \
        .eq("id", id) \
        .eq("status", "WAITING APPROVAL") \
        .execute()

    if not res.data:
        return "leave cannot be updated", 409

    return "ok", 200

# =====================
# PATCH START: API CHECK MISSED ATTENDANCE
# =====================
@app.route("/api/check-missed-attendance")
def check_missed_attendance():
    if "userid" not in session:
        return {"show": False}

    user = session["userid"]
    last_date, checkin, checkout = get_latest_absen_for_user(user)
    today = datetime.now(TZ).strftime("%Y-%m-%d")

    if not last_date:
        return {
            "show": True,
            "message": "You have not completed your attendance yet."
        }

    if last_date == today:
        return {"show": False}

    if checkin and checkout:
        return {"show": False}

    missing = []
    if not checkin:
        missing.append("Check In")
    if not checkout:
        missing.append("Check Out")

    return {
        "show": True,
        "message": (
            f"We noticed that your most recent attendance on <b>{last_date}</b> is incomplete. "
            f"Missing: <b>{', '.join(missing)}</b>. Don’t forget to complete it."
        )
    }

@app.route("/api/sisa-cuti")
def api_sisa_cuti():
    nama = request.args.get("userid")
    if not nama:
        return jsonify({"error": "nama required"}), 400

    sisa = get_sisa_cuti(nama)
    if sisa is None:
        return jsonify({
            "found": False,
            "message": "initial balance not found!"
        })

    return jsonify({
        "found": True,
        "sisa": sisa
    })
