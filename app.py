
import os
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===== In-memory "database" =====
_users = {}        # id -> {id, name}
_categories = {}   # id -> {id, name}
_records = {}      # id -> {id, user_id, category_id, created_at, amount}

_counters = {"user": 0, "category": 0, "record": 0}


def _next_id(kind: str) -> int:
    _counters[kind] += 1
    return _counters[kind]


def _error(message, status=400):
    return jsonify({"error": message}), status


@app.get("/health")
def health():
    return {"status": "ok"}


# ===== Users =====
@app.get("/user/<int:user_id>")
def get_user(user_id: int):
    user = _users.get(user_id)
    if not user:
        return _error(f"user {user_id} not found", 404)
    return user


@app.delete("/user/<int:user_id>")
def delete_user(user_id: int):
    if user_id not in _users:
        return _error(f"user {user_id} not found", 404)
    # also delete dependent records
    to_delete = [rid for rid, r in _records.items() if r["user_id"] == user_id]
    for rid in to_delete:
        _records.pop(rid, None)
    _users.pop(user_id, None)
    return {"status": "deleted", "user_id": user_id, "deleted_records": len(to_delete)}


@app.post("/user")
def create_user():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if not name or not isinstance(name, str):
        return _error("field 'name' (string) is required")
    user_id = _next_id("user")
    user = {"id": user_id, "name": name}
    _users[user_id] = user
    return user, 201


@app.get("/users")
def list_users():
    return {"items": list(_users.values()), "total": len(_users)}


# ===== Categories =====
@app.get("/category")
def list_categories():
    return {"items": list(_categories.values()), "total": len(_categories)}


@app.post("/category")
def create_category():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if not name or not isinstance(name, str):
        return _error("field 'name' (string) is required")
    # ensure unique by name (case-insensitive) for convenience
    if any(c["name"].lower() == name.lower() for c in _categories.values()):
        return _error("category with this name already exists", 409)
    cat_id = _next_id("category")
    category = {"id": cat_id, "name": name}
    _categories[cat_id] = category
    return category, 201


@app.delete("/category")
def delete_category():
    # Spec had DELETE /category (no id in path). We'll accept ?id= or JSON body {"id": n}
    cat_id = request.args.get("id", type=int)
    if cat_id is None:
        data = request.get_json(silent=True) or {}
        cat_id = data.get("id")
    if not isinstance(cat_id, int):
        return _error("category id is required (query param ?id= or JSON {'id': number})")
    if cat_id not in _categories:
        return _error(f"category {cat_id} not found", 404)
    # delete dependent records
    to_delete = [rid for rid, r in _records.items() if r["category_id"] == cat_id]
    for rid in to_delete:
        _records.pop(rid, None)
    _categories.pop(cat_id, None)
    return {"status": "deleted", "category_id": cat_id, "deleted_records": len(to_delete)}


# ===== Records =====
@app.get("/record/<int:record_id>")
def get_record(record_id: int):
    rec = _records.get(record_id)
    if not rec:
        return _error(f"record {record_id} not found", 404)
    return rec


@app.delete("/record/<int:record_id>")
def delete_record(record_id: int):
    if record_id not in _records:
        return _error(f"record {record_id} not found", 404)
    _records.pop(record_id, None)
    return {"status": "deleted", "record_id": record_id}


@app.post("/record")
def create_record():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    category_id = data.get("category_id")
    amount = data.get("amount")
    created_at = data.get("created_at")  # optional ISO8601 string

    # basic validation
    if not isinstance(user_id, int):
        return _error("field 'user_id' (int) is required")
    if not isinstance(category_id, int):
        return _error("field 'category_id' (int) is required")
    if not isinstance(amount, (int, float)):
        return _error("field 'amount' (number) is required")

    if user_id not in _users:
        return _error(f"user {user_id} not found", 404)
    if category_id not in _categories:
        return _error(f"category {category_id} not found", 404)

    if created_at is None:
        created_at = datetime.utcnow().isoformat() + "Z"
    else:
        # try to parse for sanity (very light)
        try:
            datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except Exception:
            return _error("field 'created_at' must be ISO8601 string like 2025-10-13T10:00:00Z")

    rec_id = _next_id("record")
    rec = {
        "id": rec_id,
        "user_id": user_id,
        "category_id": category_id,
        "created_at": created_at,
        "amount": float(amount),
    }
    _records[rec_id] = rec
    return rec, 201


@app.get("/record")
def list_records():
    # must accept user_id and/or category_id, and error if none present
    user_id = request.args.get("user_id", type=int)
    category_id = request.args.get("category_id", type=int)

    if user_id is None and category_id is None:
        return _error("at least one of query params 'user_id' or 'category_id' is required")

    items = list(_records.values())
    if user_id is not None:
        items = [r for r in items if r["user_id"] == user_id]
    if category_id is not None:
        items = [r for r in items if r["category_id"] == category_id]

    return {"items": items, "total": len(items)}


def create_app():
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)

@app.get("/")
def index():
    return {
        "message": "Lab2 Expenses API",
        "try": ["/health", "/users", "/category", "/record?user_id=1"]
    }

