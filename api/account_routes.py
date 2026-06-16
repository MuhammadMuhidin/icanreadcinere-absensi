from flask import jsonify, request, session

from api.app import USERS, app


@app.route("/api/me/password", methods=["PATCH"])
def change_own_password():
    user_id = session.get("userid")
    if not user_id:
        return jsonify(message="Unauthorized"), 401

    body = request.get_json(silent=True) or {}
    current_value = str(body.get("current_password") or "")
    new_value = str(body.get("new_password") or "")
    confirmation = str(body.get("confirm_password") or "")

    if not current_value:
        return jsonify(message="Current password is required"), 400
    if len(new_value) < 8:
        return jsonify(message="New password must contain at least 8 characters"), 400
    if len(new_value) > 128:
        return jsonify(message="New password is too long"), 400
    if new_value != confirmation:
        return jsonify(message="Password confirmation does not match"), 400
    if current_value == new_value:
        return jsonify(message="Choose a password different from the current password"), 400

    authenticated = USERS.authenticate(user_id, current_value)
    if not authenticated:
        return jsonify(message="Current password is incorrect"), 400

    try:
        updated = USERS.set_password(
            user_id,
            new_value,
            metadata={
                "title": session.get("title") or authenticated.get("title"),
                "phone": session.get("phone") or authenticated.get("phone"),
                "role": session.get("role") or authenticated.get("role"),
                "is_active": True,
            },
        )
    except ValueError as exc:
        return jsonify(message=str(exc)), 400
    except Exception as exc:
        print("PASSWORD UPDATE ERROR", exc)
        return jsonify(message="Password could not be saved to Supabase"), 500

    session.update(
        title=updated.get("title") or session.get("title"),
        phone=updated.get("phone"),
        role=updated.get("role") or session.get("role") or "employee",
        auth_source="supabase",
    )
    session.modified = True

    return jsonify(
        message="Password updated",
        auth_source="supabase",
        auth_table=USERS.table_name,
    )
