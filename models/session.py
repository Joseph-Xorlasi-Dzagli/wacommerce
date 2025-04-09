from datetime import datetime
from config import sessions
from utils.logger import get_logger

logger = get_logger(__name__)

def init_user_session(user_id):
    """Initialize a new user session or return existing one"""
    if user_id not in sessions:
        logger.info(f"Creating new session for user {user_id}")
        sessions[user_id] = {
            "history": [],
            "cart": [],
            "current_action": None,
            "last_context": None,
            "first_interaction": True,
            "user_name": "Customer",
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat()
        }
    else:
        # Update last active timestamp
        sessions[user_id]["last_active"] = datetime.now().isoformat()
        
    return sessions[user_id]

def update_session_history(user_id, role, content):
    """Add a message to the user's session history"""
    session = init_user_session(user_id)
    
    session["history"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })
    
    # Keep history size manageable (last 50 messages)
    if len(session["history"]) > 50:
        session["history"] = session["history"][-50:]

def is_first_time_user(user_id):
    """Check if this is the user's first interaction"""
    session = init_user_session(user_id)
    return session["first_interaction"]

def mark_user_returning(user_id):
    """Mark the user as a returning user"""
    session = init_user_session(user_id)
    session["first_interaction"] = False

def set_current_action(user_id, action):
    """Set the user's current action"""
    session = init_user_session(user_id)
    session["current_action"] = action
    logger.info(f"User {user_id} current action set to: {action}")

def get_current_action(user_id):
    """Get the user's current action"""
    session = init_user_session(user_id)
    return session["current_action"]

def set_last_context(user_id, context):
    """Set the user's last context"""
    session = init_user_session(user_id)
    session["last_context"] = context

def get_last_context(user_id):
    """Get the user's last context"""
    session = init_user_session(user_id)
    return session["last_context"]

def set_user_name(user_id, name):
    """Set the user's name"""
    session = init_user_session(user_id)
    session["user_name"] = name

def get_user_name(user_id):
    """Get the user's name"""
    session = init_user_session(user_id)
    return session["user_name"]

def get_recent_history(user_id, limit=5):
    """Get the user's recent conversation history"""
    session = init_user_session(user_id)
    return session["history"][-limit:] if session["history"] else []

def clear_session(user_id):
    """Clear a user's session data but maintain the session"""
    if user_id in sessions:
        name = sessions[user_id].get("user_name", "Customer")
        first_interaction = False
        
        # Reset but maintain user identification
        sessions[user_id] = {
            "history": [],
            "cart": [],
            "current_action": None,
            "last_context": None,
            "first_interaction": first_interaction,
            "user_name": name,
            "created_at": sessions[user_id].get("created_at", datetime.now().isoformat()),
            "last_active": datetime.now().isoformat()
        }
        return True
    return False