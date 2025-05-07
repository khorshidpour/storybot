from datetime import datetime, timedelta

# A simple in-memory session store
sessions = {}

def is_session_expired(session, minutes=15):
    last = session.get("last_active")
    if not last:
        return False
    return (datetime.utcnow() - last) > timedelta(minutes=minutes)

def start_session(user_id):
    sessions[user_id] = {
        "paid": False,
        "step": "collecting_info",
        "data": {},
        "retry": 0,
        "payment_id": "",
        "sale_id": "",
        "last_active": datetime.utcnow()
    }


def start_session(user_id):
    sessions[user_id] = {
        "paid": False,
        "step": "collecting_info",
        "data": {},
        "retry": 0,
        "payment_id": "",
        "sale_id": ""
    }

def update_session(user_id, key, value):
    if user_id in sessions:
        sessions[user_id]["data"][key] = value

def get_session(user_id):
    return sessions.get(user_id)

def save_session(user_id, session):
    # Explicitly replace the session for a user (used after editing it manually)
    sessions[user_id] = session

def mark_paid(user_id):
    if user_id in sessions:
        sessions[user_id]["paid"] = True

def mark_retry(user_id):
    if user_id in sessions:
        sessions[user_id]["retry"] += 1

def get_retry_count(user_id):
    if user_id in sessions:
        return sessions[user_id].get("retry", 0)
    return 0

def store_payment_id(user_id, payment_id):
    if user_id in sessions:
        sessions[user_id]["payment_id"] = payment_id

def store_sale_id(user_id, sale_id):
    if user_id in sessions:
        sessions[user_id]["sale_id"] = sale_id

def get_payment_id(user_id):
    return sessions.get(user_id, {}).get("payment_id", "")

def get_sale_id(user_id):
    return sessions.get(user_id, {}).get("sale_id", "")

def reset_session(user_id):
    if user_id in sessions:
        del sessions[user_id]
