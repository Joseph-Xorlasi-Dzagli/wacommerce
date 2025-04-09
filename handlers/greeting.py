from models.session import is_first_time_user, mark_user_returning, get_user_name
from models.cart import get_cart, get_cart_item_count
from services.messenger import send_button_message, send_text_message
from utils.logger import get_logger

logger = get_logger(__name__)

def handle_greeting(user_id):
    """Handle greeting intent"""
    logger.info(f"Handling greeting for user {user_id}")
    
    if is_first_time_user(user_id):
        # First-time user welcome
        welcome_message = f"👋 Welcome to our WhatsApp store! We're excited to have you shop with us. How can I help you today?"
        mark_user_returning(user_id)
    else:
        # Returning user welcome
        user_name = get_user_name(user_id)
        welcome_message = f"👋 Welcome back{' ' + user_name if user_name != 'Customer' else ''}! How can I help you today?"
        
        # Note: We no longer mention the cart items here as per requirements
    
    # Main menu buttons - removed View Cart button
    buttons = [
        {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}},
        {"type": "reply", "reply": {"id": "support", "title": "Get Help"}}
    ]
    
    send_button_message(user_id, "Welcome", welcome_message, buttons)
    return True