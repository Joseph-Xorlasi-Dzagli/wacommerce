from models.session import is_first_time_user, mark_user_returning, get_user_name
from services.messenger import send_button_message
from utils.logger import get_logger

logger = get_logger(__name__)

def handle_greeting(business_context, user_id):
    """Handle greeting intent with business context"""
    logger.info(f"Handling greeting for user {user_id}, business={business_context.get('business_id')}")
    
    # Get business-specific greeting messages
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    # Default messages
    first_time_message = f"👋 Welcome to our WhatsApp store! We're excited to have you shop with us. How can I help you today?"
    returning_message = f"👋 Welcome back! How can I help you today?"
    
    # Try to get business-specific greeting messages
    if db and business_id:
        try:
            settings_ref = db.collection('business_settings').document(business_id)
            settings_doc = settings_ref.get()
            
            if settings_doc.exists:
                settings_data = settings_doc.to_dict()
                whatsapp_settings = settings_data.get('whatsapp', {})
                
                custom_greeting = whatsapp_settings.get('greeting_message')
                if custom_greeting:
                    first_time_message = custom_greeting
                    returning_message = custom_greeting
                    
        except Exception as e:
            logger.warning(f"Could not fetch business greeting for {business_id}: {str(e)}")
    
    if is_first_time_user(user_id):
        # First-time user welcome
        welcome_message = first_time_message
        mark_user_returning(user_id)
    else:
        # Returning user welcome
        user_name = get_user_name(user_id)
        if user_name and user_name != 'Customer':
            welcome_message = f"👋 Welcome back {user_name}! How can I help you today?"
        else:
            welcome_message = returning_message
    
    # Main menu buttons
    buttons = [
        {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}},
        {"type": "reply", "reply": {"id": "support", "title": "Get Help"}}
    ]
    
    send_button_message(business_context, user_id, "Welcome", welcome_message, buttons)
    return True