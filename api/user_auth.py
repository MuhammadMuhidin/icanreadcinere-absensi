import hmac
from datetime import datetime, timezone

import bcrypt


class UserDirectory:
    """Supabase-first application user directory with USERS_JSON fallback."""

    PUBLIC_FIELDS = "user_id,title,phone,role,is_active,last_login_at"
    AUTH_FIELDS = f"{PUBLIC_FIELDS},password_hash"

    def __init__(self, client_factory, fallback_users=None, table_name="app_users"):
        self.client_factory = client_factory
        self.fallback_users = fallback_users or {}
        self.table_name = table_name

    @staticmethod
    def _normalise_db(row):
        if not row:
            return None
        return {
            "user_id": row.get("user_id"),
            "title": row.get("title") or "Team Member",
            "phone": row.get("phone"),
            "role": (row.get("role") or "employee").lower(),
            "is_active": bool(row.get("is_active", True)),
            "last_login_at": row.get("last_login_at"),
            "source": "supabase",
        }

    def _normalise_fallback(self, user_id, row):
        if not row:
            return None
        return {
            "user_id": user_id,
            "title": row.get("title") or "Team Member",
            "phone": row.get("phone"),
            "role": (row.get("role") or "employee").lower(),
            "is_active": bool(row.get("is_active", True)),
            "last_login_at": None,
            "source": "json_fallback",
        }

    def _fallback_authenticate(self, user_id, password):
        row = self.fallback_users.get(user_id)
        if not row or not row.get("is_active", True):
            return None
        expected = str(row.get("password") or "")
        supplied = str(password or "")
        if not expected or not hmac.compare_digest(expected, supplied):
            return None
        return self._normalise_fallback(user_id, row)

    def authenticate(self, user_id, password):
        """
        Supabase is authoritative when a row exists.
        JSON is consulted only when no Supabase row exists or the query fails.
        """
        try:
            rows = (
                self.client_factory()
                .table(self.table_name)
                .select(self.AUTH_FIELDS)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                row = rows[0]
                if not row.get("is_active", True):
                    return None
                password_hash = str(row.get("password_hash") or "")
                try:
                    valid = bool(password_hash) and bcrypt.checkpw(
                        str(password or "").encode("utf-8"),
                        password_hash.encode("utf-8"),
                    )
                except (ValueError, TypeError):
                    valid = False
                if not valid:
                    return None
                user = self._normalise_db(row)
                try:
                    self.client_factory().table(self.table_name).update(
                        {"last_login_at": datetime.now(timezone.utc).isoformat()}
                    ).eq("user_id", user_id).execute()
                except Exception as exc:
                    print("USER LAST LOGIN UPDATE ERROR", exc)
                return user
        except Exception as exc:
            print("SUPABASE AUTH ERROR — USING JSON FALLBACK", exc)

        return self._fallback_authenticate(user_id, password)

    def get(self, user_id):
        if not user_id:
            return None
        try:
            rows = (
                self.client_factory()
                .table(self.table_name)
                .select(self.PUBLIC_FIELDS)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                return self._normalise_db(rows[0])
        except Exception as exc:
            print("SUPABASE USER LOOKUP ERROR — USING JSON FALLBACK", exc)
        return self._normalise_fallback(user_id, self.fallback_users.get(user_id))

    def all(self):
        """Return active Supabase users plus JSON-only users during migration."""
        users = {}
        seen_in_supabase = set()
        try:
            rows = (
                self.client_factory()
                .table(self.table_name)
                .select(self.PUBLIC_FIELDS)
                .order("user_id")
                .execute()
                .data
                or []
            )
            for row in rows:
                user_id = row.get("user_id")
                if not user_id:
                    continue
                seen_in_supabase.add(user_id)
                user = self._normalise_db(row)
                if user["is_active"]:
                    users[user_id] = user
        except Exception as exc:
            print("SUPABASE USER LIST ERROR — USING JSON FALLBACK", exc)

        for user_id, row in self.fallback_users.items():
            if user_id in seen_in_supabase:
                continue
            user = self._normalise_fallback(user_id, row)
            if user and user["is_active"]:
                users[user_id] = user

        return dict(sorted(users.items(), key=lambda item: item[0].lower()))
