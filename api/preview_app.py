from datetime import date, timedelta

from flask import jsonify, session

from api.app import (
    T,
    USERS,
    app,
    attendance_rows,
    balance,
    current_user,
    grouped,
    now,
    sb,
    today,
    today_session,
)


def _own_leave_rows(user_id, limit=8):
    try:
        return (
            sb()
            .table(T("paid_leave"))
            .select("id,name,leave_date,status,reason,created_at")
            .eq("name", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print("DASHBOARD LEAVE DETAIL ERROR", exc)
        return []


def _recent_news(limit=5):
    try:
        return (
            sb()
            .table(T("news"))
            .select("content,published_at")
            .lte("published_at", date.today().isoformat())
            .order("published_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print("DASHBOARD NEWS DETAIL ERROR", exc)
        return []


def _leave_counts(rows):
    counts = {"all": len(rows), "waiting": 0, "approved": 0, "rejected": 0, "canceled": 0}
    mapping = {
        "WAITING APPROVAL": "waiting",
        "APPROVED": "approved",
        "REJECTED": "rejected",
        "CANCELED": "canceled",
    }
    for row in rows:
        key = mapping.get(row.get("status"))
        if key:
            counts[key] += 1
    return counts


@app.route("/api/me/dashboard-details")
def dashboard_details():
    user_id = session.get("userid")
    if not user_id:
        return jsonify(error="unauthorized"), 401

    directory_user = USERS.get(user_id) or current_user(user_id) or {}
    period, days, summary = grouped(user_id, now().strftime("%Y-%m"))
    today_data = today_session(user_id)
    tomorrow = (now().date() + timedelta(days=1)).isoformat()
    events = attendance_rows(user_id, today(), tomorrow)
    leave_rows = _own_leave_rows(user_id)
    announcements = _recent_news()
    complete_days = [item for item in days if item.get("state") == "completed"]
    late_days = [item for item in days if item.get("is_late")]

    return jsonify(
        profile={
            "user_id": user_id,
            "title": directory_user.get("title") or session.get("title") or "Team Member",
            "role": directory_user.get("role") or session.get("role") or "employee",
            "phone": directory_user.get("phone") or session.get("phone"),
            "auth_source": directory_user.get("source") or session.get("auth_source") or "unknown",
            "auth_table": USERS.table_name,
            "last_login_at": directory_user.get("last_login_at"),
            "leave_balance": balance(user_id),
        },
        today={
            **today_data,
            "events": events,
            "expected_start": "09:00" if now().weekday() == 5 else "10:10",
            "weekday": now().strftime("%A"),
            "date_label": now().strftime("%A, %d %B %Y"),
        },
        month={
            "period": period,
            "summary": summary,
            "recent_days": days[:6],
            "longest_day": max(complete_days, key=lambda item: item.get("duration_minutes") or 0, default=None),
            "latest_late": late_days[0] if late_days else None,
        },
        leave={
            "balance": balance(user_id),
            "counts": _leave_counts(leave_rows),
            "recent_requests": leave_rows[:5],
            "next_approved": next(
                (
                    row for row in leave_rows
                    if row.get("status") == "APPROVED"
                    and str(row.get("leave_date") or "") >= date.today().isoformat()
                ),
                None,
            ),
        },
        announcements={
            "latest": announcements[0] if announcements else None,
            "previous": announcements[1:5],
        },
    )


import api.account_routes  # noqa: E402,F401
