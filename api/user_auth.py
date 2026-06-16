import hmac
import os
from datetime import datetime, timezone

import bcrypt


class UserDirectory:
    """Supabase-first application user directory with USERS_JSON fallback."""

    PUBLIC_FIELDS = "user_id,title,phone,role,is_active,last_login_at"
    AUTH_FIELDS = f"{PUBLIC_FIELDS},password_hash"

    def __init__(self, client_factory, fallback_users=None, table_name="app_users"):
        self.client_factory = client_factory
        self.fallback_users = fallback_users or {}

        explicit_table = (os.getenv("AUTH_TABLE") or "").strip()
        suffix = (os.getenv("DB_PREFIX") or "").strip()
        if explicit_table:
            self.table_name = explicit_table
        elif table_name == "app_users":
            self.table_name = f"app_users{suffix}"
        else:
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
            print(
                f"SUPABASE AUTH ERROR ({self.table_name}) — USING JSON FALLBACK",
                exc,
            )

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
            print(
                f"SUPABASE USER LOOKUP ERROR ({self.table_name}) — USING JSON FALLBACK",
                exc,
            )
        return self._normalise_fallback(user_id, self.fallback_users.get(user_id))

    def set_password(self, user_id, new_password, metadata=None):
        """
        Store the password in Supabase, creating the row when the account still
        comes from USERS_JSON. After this succeeds, Supabase becomes authoritative.
        """
        if len(str(new_password or "")) < 8:
            raise ValueError("Password must contain at least 8 characters")

        current = self.get(user_id) or {}
        metadata = metadata or {}
        password_hash = bcrypt.hashpw(
            str(new_password).encode("utf-8"),
            bcrypt.gensalt(rounds=12),
        ).decode("utf-8")

        payload = {
            "user_id": user_id,
            "password_hash": password_hash,
            "title": metadata.get("title") or current.get("title") or "Team Member",
            "phone": metadata.get("phone") if metadata.get("phone") is not None else current.get("phone"),
            "role": (metadata.get("role") or current.get("role") or "employee").lower(),
            "is_active": bool(metadata.get("is_active", current.get("is_active", True))),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        result = (
            self.client_factory()
            .table(self.table_name)
            .upsert(payload, on_conflict="user_id")
            .execute()
        )
        if not result.data:
            raise RuntimeError("Supabase did not return the updated account")
        return self._normalise_db(result.data[0])

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
            print(
                f"SUPABASE USER LIST ERROR ({self.table_name}) — USING JSON FALLBACK",
                exc,
            )

        for user_id, row in self.fallback_users.items():
            if user_id in seen_in_supabase:
                continue
            user = self._normalise_fallback(user_id, row)
            if user and user["is_active"]:
                users[user_id] = user

        return dict(sorted(users.items(), key=lambda item: item[0].lower()))
