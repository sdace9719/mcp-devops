import os
import datetime as dt
from dataclasses import dataclass
from typing import Optional

from flask import Flask, jsonify, request
from flask_cors import CORS
import jwt
import psycopg2
from passlib.hash import bcrypt


@dataclass
class DbConfig:
    host: str
    port: int
    name: str
    user: str
    password: str


def get_db_config() -> DbConfig:
    return DbConfig(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        name=os.environ.get("DB_NAME", "appdb"),
        user=os.environ.get("DB_USER", "appuser"),
        password=os.environ.get("DB_PASSWORD", "appsecret"),
    )


def get_jwt_secret() -> str:
    return os.environ.get("JWT_SECRET", "changeme")


def get_jwt_expires_seconds() -> int:
    return int(os.environ.get("JWT_EXPIRES_IN", "86400"))


def get_db_connection():
    cfg = get_db_config()
    return psycopg2.connect(
        host=cfg.host,
        port=cfg.port,
        dbname=cfg.name,
        user=cfg.user,
        password=cfg.password,
    )


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    @app.get("/healthz")
    def healthz():
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return {"status": "ok"}
        except Exception as exc:  # noqa: BLE001
            return jsonify({"status": "error", "error": str(exc)}), 500

    def find_user_by_email(email: str) -> Optional[tuple]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, email, password FROM users WHERE email = %s", (email,))
                row = cur.fetchone()
                return row

    def create_user(email: str, password_plain: str) -> int:
        password_hash = bcrypt.hash(password_plain)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (email, password) VALUES (%s, %s) RETURNING id",
                    (email, password_hash),
                )
                new_id = cur.fetchone()[0]
                conn.commit()
                return new_id

    @app.post("/api/auth/register")
    def register():
        data = request.get_json(force=True) or {}
        email = (data.get("email") or "").strip().lower()
        password = (data.get("password") or "").strip()
        if not email or not password:
            return jsonify({"error": "email and password are required"}), 400

        existing = find_user_by_email(email)
        if existing:
            return jsonify({"error": "user already exists"}), 409

        user_id = create_user(email, password)
        return jsonify({"id": user_id, "email": email}), 201

    @app.post("/api/auth/login")
    def login():
        data = request.get_json(force=True) or {}
        email = (data.get("email") or "").strip().lower()
        password = (data.get("password") or "").strip()
        if not email or not password:
            return jsonify({"error": "email and password are required"}), 400

        user = find_user_by_email(email)
        if not user:
            return jsonify({"error": "invalid credentials"}), 401

        user_id, user_email, password_hash = user
        is_valid = False
        try:
            is_valid = bcrypt.verify(password, password_hash)
        except Exception:  # noqa: BLE001
            is_valid = False
        # Fallback for demo seed where password might be stored in plaintext
        if not is_valid and password_hash == password:
            is_valid = True
        if not is_valid:
            return jsonify({"error": "invalid credentials"}), 401

        payload = {
            "sub": str(user_id),
            "email": user_email,
            "exp": dt.datetime.utcnow() + dt.timedelta(seconds=get_jwt_expires_seconds()),
        }
        token = jwt.encode(payload, get_jwt_secret(), algorithm="HS256")
        return jsonify({"token": token})

    def require_auth() -> Optional[int]:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header.split(" ", 1)[1]
        try:
            decoded = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])  # type: ignore[no-any-unimported]
            return int(decoded.get("sub"))
        except Exception:  # noqa: BLE001
            return None

    @app.get("/api/todos")
    def list_todos():
        user_id = require_auth()
        if not user_id:
            return jsonify({"error": "unauthorized"}), 401
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, title, is_done, created_at FROM todos WHERE user_id = %s ORDER BY id DESC",
                    (user_id,),
                )
                rows = cur.fetchall()
                todos = [
                    {
                        "id": r[0],
                        "title": r[1],
                        "isDone": r[2],
                        "createdAt": r[3].isoformat(),
                    }
                    for r in rows
                ]
                return jsonify(todos)

    @app.post("/api/todos")
    def add_todo():
        user_id = require_auth()
        if not user_id:
            return jsonify({"error": "unauthorized"}), 401
        data = request.get_json(force=True) or {}
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title is required"}), 400
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO todos (user_id, title, is_done) VALUES (%s, %s, %s) RETURNING id, created_at",
                    (user_id, title, False),
                )
                row = cur.fetchone()
                conn.commit()
                return (
                    jsonify(
                        {
                            "id": row[0],
                            "title": title,
                            "isDone": False,
                            "createdAt": row[1].isoformat(),
                        }
                    ),
                    201,
                )

    @app.patch("/api/todos/<int:todo_id>")
    def toggle_todo(todo_id: int):
        user_id = require_auth()
        if not user_id:
            return jsonify({"error": "unauthorized"}), 401
        data = request.get_json(force=True) or {}
        is_done = bool(data.get("isDone", False))
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE todos SET is_done = %s WHERE id = %s AND user_id = %s RETURNING id, title, is_done, created_at",
                    (is_done, todo_id, user_id),
                )
                row = cur.fetchone()
                if not row:
                    return jsonify({"error": "not found"}), 404
                conn.commit()
                return jsonify(
                    {
                        "id": row[0],
                        "title": row[1],
                        "isDone": row[2],
                        "createdAt": row[3].isoformat(),
                    }
                )

    return app


