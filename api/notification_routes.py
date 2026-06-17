from datetime import datetime, timezone

from flask import jsonify, render_template, request, session

from api.app import T, app, ctx, sb


def _notification_rows(user_id, limit=100):
    try:
        return (
            sb()
            .table(T("notifications"))
            .select("id,user_id,type,title,message,link,metadata,read_at,created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print("NOTIFICATION LIST ERROR", exc)
        return []


def _unread_count(user_id):
    try:
        result = (
            sb()
            .table(T("notifications"))
            .select("id", count="exact")
            .eq("user_id", user_id)
            .is_("read_at", "null")
            .execute()
        )
        return result.count or 0
    except Exception as exc:
        print("NOTIFICATION COUNT ERROR", exc)
        return 0


@app.route("/inbox")
def inbox_page():
    user_id = session.get("userid")
    if not user_id:
        return app.redirect("/") if hasattr(app, "redirect") else ("Unauthorized", 401)

    notifications = _notification_rows(user_id)
    data = ctx("inbox", "Inbox")
    data.update(
        notifications=notifications,
        inbox_unread_count=sum(1 for item in notifications if not item.get("read_at")),
    )
    return render_template("inbox.html", **data)


@app.route("/api/notifications/unread-count")
def notification_unread_count():
    user_id = session.get("userid")
    if not user_id:
        return jsonify(count=0), 401
    return jsonify(count=_unread_count(user_id))


@app.route("/api/notifications/<int:notification_id>/read", methods=["PATCH"])
def mark_notification_read(notification_id):
    user_id = session.get("userid")
    if not user_id:
        return jsonify(message="Unauthorized"), 401

    read_at = datetime.now(timezone.utc).isoformat()
    try:
        result = (
            sb()
            .table(T("notifications"))
            .update({"read_at": read_at})
            .eq("id", notification_id)
            .eq("user_id", user_id)
            .is_("read_at", "null")
            .execute()
        )
    except Exception as exc:
        print("NOTIFICATION READ ERROR", exc)
        return jsonify(message="Notification could not be updated"), 500

    return jsonify(message="Notification marked as read", updated=bool(result.data))


@app.route("/api/notifications/read-all", methods=["PATCH"])
def mark_all_notifications_read():
    user_id = session.get("userid")
    if not user_id:
        return jsonify(message="Unauthorized"), 401

    read_at = datetime.now(timezone.utc).isoformat()
    try:
        result = (
            sb()
            .table(T("notifications"))
            .update({"read_at": read_at})
            .eq("user_id", user_id)
            .is_("read_at", "null")
            .execute()
        )
    except Exception as exc:
        print("NOTIFICATION READ ALL ERROR", exc)
        return jsonify(message="Notifications could not be updated"), 500

    return jsonify(message="All notifications marked as read", updated=len(result.data or []))
