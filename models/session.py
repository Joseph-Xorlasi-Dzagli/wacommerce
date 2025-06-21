from datetime import datetime, timedelta
from config import get_business_sessions, logger
from services.database import database_service
from utils.logger import get_logger

logger = get_logger(__name__)

def init_user_session(business_id, user_id):
    """Initialize a new user session or return existing one with business context"""
    
    # Try to get from database first
    if database_service:
        try:
            session_data = database_service.get_session(business_id, user_id)
            if session_data:
                logger.debug(f"Retrieved session from database for user {user_id} in business {business_id}")
                return session_data
        except Exception as e:
            logger.error(f"Error retrieving session from database: {str(e)}")
    
    # Fall back to in-memory storage
    business_sessions = get_business_sessions(business_id)
    
    if user_id not in business_sessions:
        logger.info(f"Creating new session for user {user_id} in business {business_id}")
        session_data = {
            "user_id": user_id,
            "business_id": business_id,
            "history": [],
            "cart": [],
            "current_action": None,
            "last_context": None,
            "inventory_results": None,
            "awaiting_inventory_decision": False,
            "first_interaction": True,
            "user_name": "Customer",
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat()
        }
        
        business_sessions[user_id] = session_data
        
        # Save to database if available
        if database_service:
            try:
                database_service.save_session(business_id, user_id, session_data)
            except Exception as e:
                logger.error(f"Error saving session to database: {str(e)}")
        
        return session_data
    else:
        # Update last active timestamp
        business_sessions[user_id]["last_active"] = datetime.now().isoformat()
        
        # Save updated timestamp to database
        if database_service:
            try:
                database_service.save_session(business_id, user_id, business_sessions[user_id])
            except Exception as e:
                logger.error(f"Error updating session in database: {str(e)}")
        
        return business_sessions[user_id]

def update_session_history(business_id, user_id, role, content):
    """Add a message to the user's session history with business context"""
    session = init_user_session(business_id, user_id)
    
    new_message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    }
    
    session["history"].append(new_message)
    
    # Keep history size manageable (last 50 messages)
    if len(session["history"]) > 50:
        session["history"] = session["history"][-50:]
    
    session["last_active"] = datetime.now().isoformat()
    
    # Update in-memory storage
    business_sessions = get_business_sessions(business_id)
    business_sessions[user_id] = session
    
    # Save to database if available
    if database_service:
        try:
            database_service.save_session(business_id, user_id, session)
        except Exception as e:
            logger.error(f"Error saving session history to database: {str(e)}")

def is_first_time_user(business_id, user_id):
    """Check if this is the user's first interaction with business context"""
    session = init_user_session(business_id, user_id)
    return session.get("first_interaction", True)

def mark_user_returning(business_id, user_id):
    """Mark the user as a returning user with business context"""
    session = init_user_session(business_id, user_id)
    session["first_interaction"] = False
    session["last_active"] = datetime.now().isoformat()
    
    # Update in-memory storage
    business_sessions = get_business_sessions(business_id)
    business_sessions[user_id] = session
    
    # Save to database if available
    if database_service:
        try:
            database_service.save_session(business_id, user_id, session)
        except Exception as e:
            logger.error(f"Error marking user returning in database: {str(e)}")

def set_current_action(business_id, user_id, action):
    """Set the user's current action with business context"""
    session = init_user_session(business_id, user_id)
    session["current_action"] = action
    session["last_active"] = datetime.now().isoformat()
    
    logger.info(f"User {user_id} in business {business_id} current action set to: {action}")
    
    # Update in-memory storage
    business_sessions = get_business_sessions(business_id)
    business_sessions[user_id] = session
    
    # Save to database if available
    if database_service:
        try:
            database_service.save_session(business_id, user_id, session)
        except Exception as e:
            logger.error(f"Error setting current action in database: {str(e)}")

def get_current_action(business_id, user_id):
    """Get the user's current action with business context"""
    session = init_user_session(business_id, user_id)
    return session.get("current_action")

def set_last_context(business_id, user_id, context):
    """Set the user's last context with business context"""
    session = init_user_session(business_id, user_id)
    session["last_context"] = context
    session["last_active"] = datetime.now().isoformat()
    
    # Update in-memory storage
    business_sessions = get_business_sessions(business_id)
    business_sessions[user_id] = session
    
    # Save to database if available
    if database_service:
        try:
            database_service.save_session(business_id, user_id, session)
        except Exception as e:
            logger.error(f"Error setting last context in database: {str(e)}")

def get_last_context(business_id, user_id):
    """Get the user's last context with business context"""
    session = init_user_session(business_id, user_id)
    return session.get("last_context")

def set_user_name(business_id, user_id, name):
    """Set the user's name with business context"""
    session = init_user_session(business_id, user_id)
    session["user_name"] = name
    session["last_active"] = datetime.now().isoformat()
    
    # Update in-memory storage
    business_sessions = get_business_sessions(business_id)
    business_sessions[user_id] = session
    
    # Save to database if available
    if database_service:
        try:
            database_service.save_session(business_id, user_id, session)
        except Exception as e:
            logger.error(f"Error setting user name in database: {str(e)}")

def get_user_name(business_id, user_id):
    """Get the user's name with business context"""
    session = init_user_session(business_id, user_id)
    return session.get("user_name", "Customer")

def get_recent_history(business_id, user_id, limit=5):
    """Get the user's recent conversation history with business context"""
    session = init_user_session(business_id, user_id)
    history = session.get("history", [])
    return history[-limit:] if history else []

def clear_session(business_id, user_id):
    """Clear a user's session data but maintain the session with business context"""
    session = init_user_session(business_id, user_id)
    
    # Preserve some data
    name = session.get("user_name", "Customer")
    created_at = session.get("created_at", datetime.now().isoformat())
    
    # Reset session but maintain user identification
    reset_session = {
        "user_id": user_id,
        "business_id": business_id,
        "history": [],
        "cart": [],
        "current_action": None,
        "last_context": None,
        "inventory_results": None,
        "awaiting_inventory_decision": False,
        "first_interaction": False,
        "user_name": name,
        "created_at": created_at,
        "last_active": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(hours=24)).isoformat()
    }
    
    # Update in-memory storage
    business_sessions = get_business_sessions(business_id)
    business_sessions[user_id] = reset_session
    
    # Save to database if available
    if database_service:
        try:
            database_service.save_session(business_id, user_id, reset_session)
            logger.info(f"Cleared session for user {user_id} in business {business_id}")
            return True
        except Exception as e:
            logger.error(f"Error clearing session in database: {str(e)}")
            return False
    
    return True

def set_inventory_results(business_id, user_id, inventory_results):
    """Set inventory check results in user session"""
    session = init_user_session(business_id, user_id)
    session["inventory_results"] = inventory_results
    session["awaiting_inventory_decision"] = True
    session["last_active"] = datetime.now().isoformat()
    
    # Update in-memory storage
    business_sessions = get_business_sessions(business_id)
    business_sessions[user_id] = session
    
    # Save to database if available
    if database_service:
        try:
            database_service.save_session(business_id, user_id, session)
        except Exception as e:
            logger.error(f"Error setting inventory results in database: {str(e)}")

def get_inventory_results(business_id, user_id):
    """Get inventory check results from user session"""
    session = init_user_session(business_id, user_id)
    return session.get("inventory_results")

def clear_inventory_decision(business_id, user_id):
    """Clear inventory decision state"""
    session = init_user_session(business_id, user_id)
    session["inventory_results"] = None
    session["awaiting_inventory_decision"] = False
    session["last_active"] = datetime.now().isoformat()
    
    # Update in-memory storage
    business_sessions = get_business_sessions(business_id)
    business_sessions[user_id] = session
    
    # Save to database if available
    if database_service:
        try:
            database_service.save_session(business_id, user_id, session)
        except Exception as e:
            logger.error(f"Error clearing inventory decision in database: {str(e)}")

def is_awaiting_inventory_decision(business_id, user_id):
    """Check if user is awaiting inventory decision"""
    session = init_user_session(business_id, user_id)
    return session.get("awaiting_inventory_decision", False)

def get_session_summary(business_id, user_id):
    """Get a summary of the user's session for debugging/analytics"""
    session = init_user_session(business_id, user_id)
    
    return {
        "user_id": user_id,
        "business_id": business_id,
        "user_name": session.get("user_name", "Customer"),
        "created_at": session.get("created_at"),
        "last_active": session.get("last_active"),
        "message_count": len(session.get("history", [])),
        "cart_items": len(session.get("cart", [])),
        "current_action": session.get("current_action"),
        "first_interaction": session.get("first_interaction", True),
        "awaiting_inventory_decision": session.get("awaiting_inventory_decision", False)
    }

def cleanup_expired_sessions(business_id=None):
    """Clean up expired sessions"""
    try:
        current_time = datetime.now()
        
        if business_id:
            # Clean up sessions for specific business
            business_sessions = get_business_sessions(business_id)
            expired_users = []
            
            for user_id, session in business_sessions.items():
                expires_at_str = session.get("expires_at")
                if expires_at_str:
                    try:
                        expires_at = datetime.fromisoformat(expires_at_str)
                        if current_time > expires_at:
                            expired_users.append(user_id)
                    except ValueError:
                        # Invalid date format, consider expired
                        expired_users.append(user_id)
            
            # Remove expired sessions
            for user_id in expired_users:
                del business_sessions[user_id]
                logger.info(f"Cleaned up expired session for user {user_id} in business {business_id}")
            
            return len(expired_users)
        else:
            # Clean up sessions for all businesses
            from config import business_sessions as all_business_sessions
            total_cleaned = 0
            
            for bid in list(all_business_sessions.keys()):
                cleaned = cleanup_expired_sessions(bid)
                total_cleaned += cleaned
            
            return total_cleaned
            
    except Exception as e:
        logger.error(f"Error cleaning up expired sessions: {str(e)}")