sessions = {}

def start_session(user_id):
    sessions[user_id] = {
        "paid": False,
        "step": "collecting_info",
        "data": {}
    }

def update_session(user_id, key, value):
    if user_id in sessions:
        sessions[user_id]["data"][key] = value

def get_session(user_id):
    return sessions.get(user_id)

def mark_paid(user_id):
    if user_id in sessions:
        sessions[user_id]["paid"] = True

def reset_session(user_id):
    if user_id in sessions:
        del sessions[user_id]
