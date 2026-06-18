from collections import defaultdict
from datetime import date, datetime, timedelta
from io import StringIO
from math import atan2, cos, radians, sin, sqrt
import boto3, csv, json, os, pytz, requests
from dateutil.parser import isoparse
from flask import Flask, Response, flash, jsonify, redirect, render_template, request, session
from supabase import create_client

try:
    from api.user_auth import UserDirectory
except ImportError:
    from user_auth import UserDirectory

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__, template_folder=os.path.join(ROOT, "templates"), static_folder=os.path.join(ROOT, "static"))
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")
app.permanent_session_lifetime = timedelta(days=7)
TZ = pytz.timezone("Asia/Jakarta")
GAS_URL = os.getenv("GAS_URL")
PREFIX = os.getenv("DB_PREFIX", "")
AUTH_TABLE = os.getenv("AUTH_TABLE", "app_users")
R2_PUBLIC_BASE_URL = os.getenv("R2_PUBLIC_BASE_URL", "")
_UNSET = object()

try:
    FALLBACK_USERS = json.loads(os.environ.get("USERS_JSON", "{}"))
    if not isinstance(FALLBACK_USERS, dict):
        FALLBACK_USERS = {}
except Exception as exc:
    print("USERS_JSON ERROR", exc)
    FALLBACK_USERS = {}

_sb = _r2 = None


def T(name): return f"{name}{PREFIX}"
def now(): return datetime.now(TZ)
def today(): return now().strftime("%Y-%m-%d")


def sb():
    global _sb
    if _sb is None:
        url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ROLE_KEY")
        if not url or not key: raise RuntimeError("Supabase credentials not set")
        _sb = create_client(url, key)
    return _sb


USERS = UserDirectory(sb, FALLBACK_USERS, AUTH_TABLE)


def current_user(uid=None):
    target = uid or session.get("userid")
    if target and target == session.get("userid") and session.get("role"):
        return {
            "user_id": target,
            "title": session.get("title", "Team Member"),
            "phone": session.get("phone"),
            "role": session.get("role", "employee"),
            "is_active": True,
            "source": session.get("auth_source", "session"),
        }
    return USERS.get(target)


def manager(uid):
    data = current_user(uid) or {}
    role = str(data.get("role", "")).lower()
    title = str(data.get("title", "")).lower()
    return role in {"manager", "admin"} or "manager" in title or uid == "Hanny"


def admin(uid):
    data = current_user(uid) or {}
    role = str(data.get("role", "")).lower()
    return role == "admin" or uid in {"Hanny", "Mita"} or manager(uid)


def r2():
    global _r2
    if _r2 is None:
        endpoint, key, secret = os.getenv("R2_ENDPOINT"), os.getenv("R2_KEY"), os.getenv("R2_SECRET")
        if not endpoint or not key or not secret: raise RuntimeError("R2 credentials not set")
        _r2 = boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=key, aws_secret_access_key=secret)
    return _r2


def ctx(page, title):
    uid = session.get("userid")
    return dict(active_page=page, page_title=title, is_manager=manager(uid), can_admin_tools=admin(uid), current_user=uid,
                current_title=session.get("title", ""), R2_PUBLIC_BASE_URL=R2_PUBLIC_BASE_URL)


def news():
    try:
        rows = sb().table(T("news")).select("content,published_at").lte("published_at", date.today().isoformat()).order("published_at", desc=True).limit(1).execute().data
        if rows: return rows[0]
    except Exception as exc: print("NEWS ERROR", exc)
    return {"content": "Welcome to Attendance System", "published_at": None}


def balance(uid):
    try:
        rows = sb().table(T("balance")).select("sisa").eq("nama", uid).limit(1).execute().data
        return int(rows[0]["sisa"]) if rows else None
    except Exception as exc: print("BALANCE ERROR", exc); return None



def create_notification(user_id, type, title, message, link=None, metadata=None):
    try:
        # Jika link tidak diisi atau None, otomatis arahkan ke halaman utama "/" atau "#"
        final_link = link if link is not None else "/" 
        
        sb().table(T("notifications")).insert({
            "user_id": user_id,
            "type": type,
            "title": title,
            "message": message,
            "link": final_link, # <--- Menggunakan final_link yang aman
            "metadata": metadata or {},
        }).execute()
    except Exception as exc:
        print("NOTIFICATION ERROR", exc)



def office():
    try: return tuple(float(x.strip()) for x in os.getenv("POINTOFFICE", "").split(",", 1))
    except Exception as exc: raise RuntimeError("POINTOFFICE env is invalid") from exc


def distance(a, b, c, d):
    radius, dlat, dlon = 6371000, radians(c-a), radians(d-b)
    value = sin(dlat/2)**2 + cos(radians(a))*cos(radians(c))*sin(dlon/2)**2
    return 2*radius*atan2(sqrt(value), sqrt(1-value))


def late_status(value):
    current = value if not isinstance(value, str) else datetime.strptime(value, "%H:%M:%S").time()
    limit = datetime.strptime("09:00:00" if now().weekday() == 5 else "10:10:00", "%H:%M:%S").time()
    if current <= limit: return "On time!"
    seconds = int((datetime.combine(now().date(), current)-datetime.combine(now().date(), limit)).total_seconds())
    return f"{seconds//3600:02}:{seconds%3600//60:02}:{seconds%60:02}"


def attendance_rows(uid, start, end):
    try:
        return sb().table(T("log_absen")).select("id,nama,aksi,tanggal,waktu,deviation,mood,notes").eq("nama", uid).gte("tanggal", start).lt("tanggal", end).order("tanggal", desc=True).order("waktu", desc=False).execute().data or []
    except Exception as exc: print("ATTENDANCE ERROR", exc); return []


def day_session(rows, day=None):
    checkin = checkout = None; deviation = mood = notes = ""
    for row in rows:
        action = str(row.get("aksi", "")).lower()
        if action == "check in" and checkin is None:
            checkin, deviation = row.get("waktu"), row.get("deviation") or ""
            mood, notes = row.get("mood") or mood, row.get("notes") or notes
        elif action == "check out":
            checkout, mood, notes = row.get("waktu"), row.get("mood") or mood, row.get("notes") or notes
    state = "not_started" if not checkin else "checked_in" if not checkout else "completed"
    duration = None
    if checkin and checkout:
        try: duration = max(0, int((datetime.strptime(checkout[:8], "%H:%M:%S")-datetime.strptime(checkin[:8], "%H:%M:%S")).total_seconds()//60))
        except Exception: pass
    return dict(date=day or (rows[0].get("tanggal") if rows else today()), checkin=checkin, checkout=checkout,
                deviation=deviation, mood=mood, notes=notes, state=state, duration_minutes=duration,
                is_late=bool(deviation and deviation != "On time!"))


def today_session(uid, rows=None):
    day = today()
    if rows is None:
        tomorrow = (now().date()+timedelta(days=1)).isoformat()
        rows = attendance_rows(uid, day, tomorrow)
    else:
        rows = [row for row in rows if row.get("tanggal") == day]
    return day_session(rows, day)


def bounds(period=None):
    try: start = datetime.strptime(period or "", "%Y-%m").date().replace(day=1)
    except ValueError: start = now().date().replace(day=1)
    end = date(start.year+1, 1, 1) if start.month == 12 else date(start.year, start.month+1, 1)
    return start, end


def grouped_from_rows(rows, period=None):
    start, end = bounds(period)
    start_value, end_value = start.isoformat(), end.isoformat()
    bucket = defaultdict(list)
    for row in rows:
        day = row.get("tanggal")
        if day and start_value <= day < end_value:
            bucket[day].append(row)
    days = sorted((day_session(day_rows, day) for day, day_rows in bucket.items()), key=lambda x:x["date"], reverse=True)
    completed = [x for x in days if x["state"] == "completed"]; late = [x for x in days if x["is_late"]]
    late_minutes = 0
    for item in late:
        try:
            h,m,s = map(int, item["deviation"].split(":")); late_minutes += h*60+m+(s>=30)
        except Exception: pass
    durations = [x["duration_minutes"] for x in completed if x["duration_minutes"] is not None]
    summary = dict(recorded_days=len(days), completed_days=len(completed), on_time_days=sum(x["deviation"]=="On time!" for x in days),
                   late_days=len(late), incomplete_days=sum(x["state"]=="checked_in" for x in days), total_late_minutes=late_minutes,
                   total_work_minutes=sum(durations), average_work_minutes=round(sum(durations)/len(durations)) if durations else 0)
    return start.strftime("%Y-%m"), days, summary


def grouped(uid, period=None):
    start, end = bounds(period)
    rows = attendance_rows(uid, start.isoformat(), end.isoformat())
    return grouped_from_rows(rows, period)


def last_incomplete(uid, rows=None):
    if rows is None:
        start, end = now().date()-timedelta(days=45), now().date()+timedelta(days=1)
        rows = attendance_rows(uid, start.isoformat(), end.isoformat())
    bucket = defaultdict(list)
    cutoff = (now().date()-timedelta(days=45)).isoformat()
    for row in rows:
        day = row.get("tanggal")
        if day and day >= cutoff:
            bucket[day].append(row)
    for day in sorted(bucket, reverse=True):
        item = day_session(bucket[day], day)
        if day != today() and item["state"] == "checked_in": return item
    return None


def leave_rows(uid):
    query = sb().table(T("paid_leave")).select("*").order("created_at", desc=True)
    if not manager(uid): query = query.eq("name", uid)
    return query.execute().data or []


def leave_summary(uid, data=None, balance_value=_UNSET):
    data = leave_rows(uid) if data is None else data
    balance_value = balance(uid) if balance_value is _UNSET else balance_value
    result = dict(all=len(data), waiting=0, approved=0, rejected=0, canceled=0, balance=balance_value)
    for item in data:
        key = {"WAITING APPROVAL":"waiting", "APPROVED":"approved", "REJECTED":"rejected", "CANCELED":"canceled"}.get(item.get("status"))
        if key: result[key] += 1
    return result


def periods():
    try: return [x["period"] for x in (sb().rpc("get_last_periods").execute().data or []) if x.get("period")]
    except Exception as exc: print("PERIOD ERROR", exc); return []


def team_today():
    names_dict = USERS.all()
    names = list(names_dict.keys())
    day = today()
    by_name = defaultdict(list)

    # Retry up to 2 times for log_absen query
    rows = []
    log_error = None
    for attempt in range(2):
        try:
            rows = sb().table(T("log_absen")).select("nama,aksi,tanggal,waktu,deviation,mood,notes").eq("tanggal", day).order("waktu", desc=False).execute().data or []
            log_error = None
            break
        except Exception as exc:
            log_error = str(exc)
            print(f"TEAM LOG_ABSEN ERROR (attempt {attempt+1})", exc)
    if log_error:
        flash("Could not load attendance records. Some statuses may be inaccurate.", "error")

    for row in rows:
        by_name[row.get("nama")].append(row)

    # Retry up to 2 times for paid_leave query
    leave_names = set()
    leave_error = None
    for attempt in range(2):
        try:
            leave_rows = sb().table(T("paid_leave")).select("name").eq("leave_date", day).eq("status", "APPROVED").execute().data or []
            leave_names = {x.get("name") for x in leave_rows}
            leave_error = None
            break
        except Exception as exc:
            leave_error = str(exc)
            print(f"TEAM PAID_LEAVE ERROR (attempt {attempt+1})", exc)
    if leave_error:
        flash("Could not load leave records. Leave statuses may be inaccurate.", "error")

    # Only count leaves for users that actually exist in the directory
    leave_names = leave_names & set(names)

    counts = dict(checked_in=0, completed=0, on_time=0, late=0, not_started=0, on_leave=len(leave_names))
    people = []
    for name in names:
        if name in leave_names:
            people.append(dict(name=name, status="on_leave", label="Approved leave", checkin=None, checkout=None, deviation=""))
            continue
        item = day_session(by_name.get(name, []), day)
        counts[item["state"]] += 1
        counts["on_time"] += item["deviation"] == "On time!"
        counts["late"] += item["is_late"]
        people.append(dict(name=name, status=item["state"], checkin=item["checkin"], checkout=item["checkout"], deviation=item["deviation"]))

    order = {"checked_in": 0, "not_started": 1, "on_leave": 2, "completed": 3}
    people.sort(key=lambda x: (order.get(x["status"], 9), x["name"]))
    return {"date": day, "counts": counts, "people": people, "log_error": bool(log_error), "leave_error": bool(leave_error)}


@app.before_request
def permanent(): session.permanent = True


@app.after_request
def headers(response):
    if request.endpoint == "login":
        response.headers.update({"Cache-Control":"no-store, no-cache, must-revalidate","Pragma":"no-cache","Expires":"0"})
    return response


@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        uid, password = (request.form.get("userid") or "").strip(), request.form.get("password") or ""
        user = USERS.authenticate(uid, password)
        if user:
            session.clear()
            session.update(
                userid=user["user_id"],
                title=user.get("title") or "Team Member",
                phone=user.get("phone"),
                role=user.get("role") or "employee",
                auth_source=user.get("source") or "unknown",
            )
            return redirect("/absence")
        flash("Incorrect user ID or password.","error")
    if session.get("userid"): return redirect("/absence")
    return render_template("signin.html",news=news())


@app.route("/logout", methods=["GET","POST"])
def logout(): session.clear(); return redirect("/")


@app.route("/absence", methods=["GET","POST"])
def absence():
    uid=session.get("userid")
    if not uid: return redirect("/")
    if request.method == "POST":
        action=(request.form.get("aksi") or "").strip(); mood=(request.form.get("mood") or "Neutral").strip(); notes=(request.form.get("notes") or "").strip()[:500]
        current=today_session(uid)
        invalid = action not in {"Check In","Check Out"} or (action=="Check In" and current["state"]!="not_started") or (action=="Check Out" and current["state"]!="checked_in")
        if invalid: flash("This attendance action is not available now.","error"); return redirect("/absence")
        try: lat,lon,accuracy=float(request.form.get("latitude","")),float(request.form.get("longitude","")),float(request.form.get("accuracy","0") or 0)
        except ValueError: flash("We could not read your location.","error"); return redirect("/absence")
        olat,olon=office(); meters=distance(lat,lon,olat,olon)
        if meters>150: flash(f"You are approximately {round(meters)} metres from the office.","error"); return redirect("/absence")
        if accuracy and accuracy>120: flash("Location accuracy is too low. Try again in an open area.","error"); return redirect("/absence")
        stamp=now(); deviation=late_status(stamp.time()) if action=="Check In" else ""
        try:
            saved=sb().table(T("log_absen")).insert(dict(nama=uid,aksi=action,tanggal=stamp.strftime("%Y-%m-%d"),waktu=stamp.strftime("%H:%M:%S"),deviation=deviation,mood=mood,notes=notes)).execute()
            if not saved.data: raise RuntimeError("No data returned")
        except Exception as exc: flash(f"Attendance could not be saved: {exc}","error"); return redirect("/absence")
        try: requests.post(GAS_URL,json=dict(nama=uid,aksi=action,late_status=deviation,mood=mood,notes=notes),timeout=5)
        except Exception as exc: print("GAS ERROR",exc)
        detail="on time" if deviation=="On time!" else f"late by {deviation[:5]}" if deviation else "recorded"
        flash(f"{action} recorded at {stamp.strftime('%H:%M')} — {detail}.","success"); return redirect("/absence")

    current_date = now().date()
    attendance_start = current_date-timedelta(days=45)
    attendance_end = current_date+timedelta(days=1)
    attendance_data = attendance_rows(uid, attendance_start.isoformat(), attendance_end.isoformat())
    period,days,summary = grouped_from_rows(attendance_data, current_date.strftime("%Y-%m"))
    current_balance = balance(uid)
    leave_data = leave_rows(uid)

    data=ctx("home","Attendance")
    data.update(
        nama=uid,
        title=session.get("title","Team Member"),
        today_session=today_session(uid, attendance_data),
        month_period=period,
        month_summary=summary,
        news=news(),
        sisa=current_balance,
        leave_summary=leave_summary(uid, leave_data, current_balance),
        latest_incomplete=last_incomplete(uid, attendance_data),
    )
    return render_template("absence.html",**data)


@app.route("/history")
def history():
    uid=session.get("userid")
    if not uid: return redirect("/")
    period,days,summary=grouped(uid,request.args.get("period")); data=ctx("history","Attendance history"); data.update(period=period,attendance_rows=days,summary=summary)
    return render_template("history.html",**data)


@app.route("/api/me/attendance/history")
def attendance_history_api():
    uid=session.get("userid")
    if not uid: return jsonify(error="unauthorized"),401
    period,days,summary=grouped(uid,request.args.get("period")); return jsonify(period=period,data=days,summary=summary)


@app.route("/api/me/attendance/summary")
def attendance_summary_api():
    uid=session.get("userid")
    if not uid: return jsonify(error="unauthorized"),401
    period,_,summary=grouped(uid,request.args.get("period")); return jsonify(period=period,summary=summary)


@app.route("/change_photo",methods=["POST"])
def change_photo():
    uid=session.get("userid")
    if not uid: return Response(status=401)
    file=request.files.get("file")
    if not file: return jsonify(message="No file selected"),400
    if file.mimetype not in {"image/jpeg","image/png","image/webp"}: return jsonify(message="Use a JPG, PNG or WebP image"),400
    payload=file.read()
    if len(payload)>5*1024*1024: return jsonify(message="Image must be smaller than 5 MB"),400
    r2().put_object(Bucket=os.getenv("R2_BUCKET"),Key=f"profiles/{uid}.jpg",Body=payload,ContentType=file.mimetype)
    return jsonify(message="Profile photo updated")


@app.route("/paid_leave")
def paid_leave():
    uid=session.get("userid")
    if not uid: return redirect("/")
    day=now().date()
    current_balance = balance(uid)
    leave_data = leave_rows(uid)
    data=ctx("leave","Paid leave")
    data.update(
        SESSION_NAME=uid,
        leave_balance=current_balance,
        leave_summary=leave_summary(uid, leave_data, current_balance),
        min_leave_date=day.isoformat(),
        max_leave_date=(day+timedelta(days=30)).isoformat(),
    )
    return render_template("paid_leave.html",**data)


@app.route("/leave",methods=["GET"])
def get_leave():
    uid=session.get("userid")
    return (jsonify(data=leave_rows(uid)),200) if uid else (jsonify(error="unauthorized"),401)


@app.route("/api/me/leave-summary")
def leave_summary_api():
    uid=session.get("userid"); return jsonify(leave_summary(uid)) if uid else (jsonify(error="unauthorized"),401)


@app.route("/leave",methods=["POST"])
def submit_leave():
    uid=session.get("userid")
    if not uid: return jsonify(error="unauthorized"),401
    raw=(request.get_json(silent=True) or {}).get("leave_date")
    try: chosen=isoparse(raw).date()
    except Exception: return jsonify(message="Invalid leave date"),400
    day=now().date()
    if chosen<day or (chosen-day).days>30: return jsonify(message="Choose a date within the next 30 days"),400
    sb().table(T("paid_leave")).insert(dict(name=uid,leave_date=chosen.isoformat(),status="WAITING APPROVAL")).execute()
    create_notification(
        user_id="Hanny",
        type="manager_action",
        title="Leave approval required",
        message=f"{uid} submitted a leave request for {chosen.isoformat()}.",
        link="/paid_leave"
    )
    return jsonify(message="Leave request submitted"),201


@app.route("/leave/<int:leave_id>/cancel",methods=["PATCH"])
def cancel_leave(leave_id):
    uid=session.get("userid")
    if not uid: return jsonify(error="unauthorized"),401
    row=sb().table(T("paid_leave")).select("name,status").eq("id",leave_id).single().execute().data
    if not row: return jsonify(message="Request not found"),404
    if row.get("name")!=uid: return jsonify(message="You cannot cancel this request"),403
    if row.get("status")!="WAITING APPROVAL": return jsonify(message="Only waiting requests can be canceled"),400
    sb().table(T("paid_leave")).update({"status":"CANCELED"}).eq("id",leave_id).execute(); create_notification(uid,"leave_cancelled","Leave request cancelled","Your leave request has been cancelled.","/paid_leave"); return jsonify(message="Leave request canceled")


@app.route("/leave/<int:leave_id>/decision",methods=["PATCH"])
def decide_leave(leave_id):
    if not manager(session.get("userid")): return jsonify(message="Forbidden"),403
    body=request.get_json(silent=True) or {}; action,reason=body.get("action"),str(body.get("reason","")).strip()
    if action not in {"APPROVED","REJECTED"} or (action=="REJECTED" and not reason): return jsonify(message="Invalid decision"),400
    row=sb().table(T("paid_leave")).select("name,status,leave_date").eq("id",leave_id).single().execute().data
    if not row: return jsonify(message="Request not found"),404
    if row.get("status")!="WAITING APPROVAL": return jsonify(message="Request has already been processed"),400
    name=row["name"]
    if action=="APPROVED":
        current=balance(name)
        if current is None or current<=0: return jsonify(message="Employee has no leave balance"),400
        sb().table(T("balance")).update({"sisa":current-1}).eq("nama",name).execute()
        patch={"status":"APPROVED","reason":None}
    else: patch={"status":"REJECTED","reason":reason}
    sb().table(T("paid_leave")).update(patch).eq("id",leave_id).eq("status","WAITING APPROVAL").execute()
    create_notification(
        name,
        "leave_approved" if action=="APPROVED" else "leave_rejected",
        "Leave request approved" if action=="APPROVED" else "Leave request rejected",
        f"Your leave request for {row['leave_date']} has been {'approved' if action=='APPROVED' else 'rejected'}.",
        "/paid_leave"
    )
    phone=(USERS.get(name) or {}).get("phone")
    if phone:
        try:
            requests.post(os.getenv("SVR_MSG"),headers={"x-api-key":os.getenv("SEND_API_KEY")},json={"to":phone,"msg":f"Your leave request for {row['leave_date']} is {action.lower()}.",},timeout=10)
        except Exception: pass
    return jsonify(message=action.title())


@app.route("/leave/<int:leave_id>",methods=["PATCH"])
def edit_leave(leave_id):
    uid=session.get("userid")
    if not uid: return jsonify(message="Unauthorized"),401
    try: chosen=isoparse((request.get_json(silent=True) or {}).get("leave_date")).date()
    except Exception: return jsonify(message="Invalid leave date"),400
    day=now().date()
    if chosen<day or (chosen-day).days>30: return jsonify(message="Choose a date within the next 30 days"),400
    result=sb().table(T("paid_leave")).update({"leave_date":chosen.isoformat()}).eq("id",leave_id).eq("name",uid).eq("status","WAITING APPROVAL").execute()
    return jsonify(message="Leave date updated") if result.data else (jsonify(message="Request cannot be updated"),409)


@app.route("/api/leave/wait-count")
def wait_count():
    if not manager(session.get("userid")): return jsonify(count=0),403
    result=sb().table(T("paid_leave")).select("id",count="exact").eq("status","WAITING APPROVAL").execute(); return jsonify(count=result.count or 0)


@app.route("/manager")
def manager_page():
    if not manager(session.get("userid")): return redirect("/absence")
    data=ctx("manager","Team today"); data.update(dashboard=team_today()); return render_template("manager.html",**data)


@app.route("/api/manager/today")
def team_api(): return jsonify(team_today()) if manager(session.get("userid")) else (jsonify(message="Forbidden"),403)


@app.route("/upload",methods=["GET","POST"])
def upload():
    uid=session.get("userid")
    if not admin(uid): return redirect("/absence")
    if request.method=="POST":
        if not USERS.authenticate(uid, request.form.get("password") or ""):
            flash("Incorrect admin password.","error"); return redirect("/upload")
        kind=request.form.get("jenis")
        try:
            if kind=="banner":
                content=(request.form.get("content") or "").strip()
                if not content: flash("Announcement content is required.","error"); return redirect("/upload?tab=announcement")
                published=date.today().isoformat()
                if request.form.get("publish_mode")=="schedule":
                    scheduled=date.fromisoformat(request.form.get("published_at"))
                    if scheduled<date.today(): flash("Scheduled date must be today or later.","error"); return redirect("/upload?tab=announcement")
                    published=scheduled.isoformat()
                sb().table(T("news")).insert({"content":content,"published_at":published}).execute();
                for user in USERS.all().values():
                    target_id = user.get("userid") or user.get("user_id")
                    create_notification(
                        user_id=target_id,
                        type="announcement",
                        title="Announcement",
                        message=content,
                        link=None
                    )
                flash("Announcement saved.","success"); return redirect("/upload?tab=announcement")
            if kind=="cuti" and manager(uid):
                name,value=request.form.get("userid"),request.form.get("sisa")
                result=sb().table(T("balance")).update({"sisa":int(value)}).eq("nama",name).execute(); flash("Leave balance updated." if result.data else "Employee balance was not found.","success" if result.data else "error"); return redirect("/upload?tab=balance")
        except Exception as exc: print("ADMIN ERROR",exc); flash("The operation could not be completed.","error"); return redirect("/upload")
    day=date.today().isoformat(); scheduled=sb().table(T("news")).select("content,published_at").gt("published_at",day).order("published_at",desc=False).execute().data or []
    employees=sorted(({"name":name,"title":item.get("title","Team Member")} for name,item in USERS.all().items()),key=lambda x:x["name"])
    data=ctx("admin","Admin tools"); data.update(scheduled_news=scheduled,employees=employees,periods=periods(),selected_tab=request.args.get("tab","announcement"),today=day)
    return render_template("upload.html",**data)


@app.route("/api/sisa-cuti")
def balance_api():
    uid=session.get("userid")
    if not uid: return jsonify(error="unauthorized"),401
    name=request.args.get("userid") or uid
    if name!=uid and not manager(uid): return jsonify(error="forbidden"),403
    value=balance(name); return jsonify(found=value is not None,sisa=value,message=None if value is not None else "Initial balance not found")


@app.route("/api/check-period")
def periods_api(): return jsonify(periods=periods()) if manager(session.get("userid")) else (jsonify(error="Unauthorized"),403)


@app.route("/api/check-missed-attendance")
def missed_api():
    uid=session.get("userid")
    if not uid: return jsonify(show=False)
    item=last_incomplete(uid)
    return jsonify(show=False) if not item else jsonify(show=True,date=item["date"],missing="Check Out",message=f"Your attendance on {item['date']} has no check-out record.")


@app.route("/download-absen")
def download():
    if not manager(session.get("userid")): return "Unauthorized",403
    period=request.args.get("periode")
    if not period: return "Period is required",400
    start,end=bounds(period); rows=sb().table(T("log_absen")).select("tanggal,waktu,nama,aksi,deviation,mood,notes").gte("tanggal",start.isoformat()).lt("tanggal",end.isoformat()).order("tanggal",desc=False).order("waktu",desc=False).execute().data or []
    if not rows: return "No attendance data found",404
    output=StringIO(); writer=csv.DictWriter(output,fieldnames=rows[0].keys(),delimiter=";"); writer.writeheader(); writer.writerows(rows)
    return Response(output.getvalue(),mimetype="text/csv",headers={"Content-Disposition":f"attachment; filename=attendance_{period}.csv"})


try:
    import api.notification_routes
except Exception as exc:
    print('NOTIFICATION ROUTES LOAD ERROR', exc)
