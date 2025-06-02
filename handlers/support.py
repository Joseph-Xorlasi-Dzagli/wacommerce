from services.messenger import send_text_message, send_button_message, send_list_message
from models.session import set_current_action
from utils.logger import get_logger

logger = get_logger(__name__)

def handle_support(user_id):
    """Handle customer support intent"""
    logger.info(f"Handling support for user {user_id}")
    
    # Show support options
    support_options = [
        {"id": "support_faq", "title": "Frequently Asked Questions", "description": "Common questions and answers"},
        {"id": "support_shipping", "title": "Shipping Information", "description": "Shipping policies and timeframes"},
        {"id": "support_returns", "title": "Returns & Refunds", "description": "Our return and refund policies"},
        {"id": "support_contact", "title": "Contact Support Team", "description": "Get in touch with our customer service"}
    ]
    
    sections = [{
        "title": "Support Options",
        "rows": support_options
    }]
    
    send_list_message(
        user_id,
        "Customer Support",
        "How can we help you today?",
        "Select an Option",
        sections
    )
    
    return True

def handle_support_faq(user_id):
    """Handle FAQ support option"""
    logger.info(f"Handling FAQ for user {user_id}")
    
    faq_text = (
        "*Frequently Asked Questions*\n\n"
        "*How long does shipping take?*\n"
        "Standard shipping takes 3-5 business days. Express shipping takes 1-2 business days.\n\n"
        
        "*Do you ship internationally?*\n"
        "Yes, we ship to most countries worldwide. International shipping typically takes 7-14 business days.\n\n"
        
        "*How can I track my order?*\n"
        "You'll receive a tracking number via WhatsApp once your order ships. You can also check your order status by sending 'order status'.\n\n"
        
        "*What payment methods do you accept?*\n"
        "We accept credit/debit cards, PayPal, bank transfers, and cash on delivery (where available).\n\n"
        
        "*How do I return an item?*\n"
        "Contact our support team within 30 days of receiving your order. We'll guide you through the return process."
    )
    
    send_text_message(user_id, faq_text)
    
    # Offer additional help
    buttons = [
        {"type": "reply", "reply": {"id": "support", "title": "More Help Options"}},
        {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
    ]
    
    send_button_message(
        user_id,
        "More Questions?",
        "Can we help with anything else?",
        buttons
    )
    
    return True

def handle_support_shipping(user_id):
    """Handle shipping information support option"""
    logger.info(f"Handling shipping info for user {user_id}")
    
    shipping_text = (
        "*Shipping Information*\n\n"
        "*Standard Shipping (Free)*\n"
        "• Delivery in 3-5 business days\n"
        "• Available for all domestic orders\n"
        "• Free for orders over GHS50\n\n"
        
        "*Express Shipping (GHS9.99)*\n"
        "• Delivery in 1-2 business days\n"
        "• Available for domestic orders placed before 2PM\n"
        "• Includes weekend delivery\n\n"
        
        "*International Shipping*\n"
        "• Delivery in 7-14 business days\n"
        "• Shipping costs vary by destination\n"
        "• Customs fees may apply\n\n"
        
        "*Store Pickup (Free)*\n"
        "• Available for collection same day if ordered before 3PM\n"
        "• Please bring ID and order number"
    )
    
    send_text_message(user_id, shipping_text)
    
    # Offer additional help
    buttons = [
        {"type": "reply", "reply": {"id": "support", "title": "More Help Options"}},
        {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
    ]
    
    send_button_message(
        user_id,
        "More Questions?",
        "Can we help with anything else?",
        buttons
    )
    
    return True

def handle_support_returns(user_id):
    """Handle returns and refunds support option"""
    logger.info(f"Handling returns info for user {user_id}")
    
    returns_text = (
        "*Returns & Refunds Policy*\n\n"
        "*Return Eligibility*\n"
        "• 30-day return window from delivery date\n"
        "• Items must be unused and in original packaging\n"
        "• Receipt or order confirmation required\n\n"
        
        "*Return Process*\n"
        "1. Contact our support team\n"
        "2. Receive return authorization and instructions\n"
        "3. Ship items back with provided return label\n"
        "4. Refund processed within 5-7 business days after receiving return\n\n"
        
        "*Refunds*\n"
        "• Original payment method will be refunded\n"
        "• Shipping costs are non-refundable\n"
        "• Return shipping is free for defective items\n\n"
        
        "*Exceptions*\n"
        "• Personalized items cannot be returned\n"
        "• Downloadable products are non-refundable\n"
        "• Sale items may have different return conditions"
    )
    
    send_text_message(user_id, returns_text)
    
    # Offer additional help
    buttons = [
        {"type": "reply", "reply": {"id": "support", "title": "More Help Options"}},
        {"type": "reply", "reply": {"id": "support_contact", "title": "Contact Support"}}
    ]
    
    send_button_message(
        user_id,
        "Need to Return Something?",
        "Our support team can help with your return.",
        buttons
    )
    
    return True

def handle_support_contact(user_id):
    """Handle contact support team option"""
    logger.info(f"Handling contact support for user {user_id}")
    
    contact_text = (
        "*Contact Our Support Team*\n\n"
        "Our customer service team is here to help!\n\n"
        
        "*Support Hours:*\n"
        "Monday-Friday: 9AM-6PM\n"
        "Saturday: 10AM-4PM\n"
        "Sunday: Closed\n\n"
        
        "*Contact Options:*\n"
        "• Email: support@example.com\n"
        "• Phone: 1-800-123-4567\n"
        "• Live Chat: www.example.com/support\n\n"
        
        "You can also continue this conversation with a support agent. Would you like us to connect you with a live agent?"
    )
    
    send_text_message(user_id, contact_text)
    
    # Offer to connect with an agent
    buttons = [
        {"type": "reply", "reply": {"id": "connect_agent", "title": "Connect with Agent"}},
        {"type": "reply", "reply": {"id": "browse", "title": "Continue Shopping"}}
    ]
    
    send_button_message(
        user_id,
        "Live Support",
        "Would you like to speak with a customer service agent?",
        buttons
    )
    
    return True

def handle_connect_agent(user_id):
    """Handle request to connect with an agent"""
    logger.info(f"Handling agent connection for user {user_id}")
    
    # In a real implementation, this would transfer to a live agent system
    # For demo purposes, we'll simulate the transfer
    
    send_text_message(
        user_id,
        "I'm connecting you with a customer service agent. Please wait a moment while an agent becomes available."
    )
    
    # Set action to indicate waiting for agent
    set_current_action(user_id, "awaiting_agent")
    
    # Simulate agent response after a delay
    # In a real implementation, this would hand off to a different system
    send_text_message(
        user_id,
        "👨‍💼 *Agent Sarah:* Hello! This is Sarah from customer support. How can I help you today?"
    )
    
    # Reset action
    set_current_action(user_id, None)
    
    return True

def handle_feedback(user_id):
    """Handle customer feedback intent"""
    logger.info(f"Handling feedback for user {user_id}")
    
    send_text_message(
        user_id,
        "We value your feedback! Please share your thoughts, suggestions, or experiences with our products and service."
    )
    
    # Set action
    set_current_action(user_id, "awaiting_feedback")
    
    return True

def handle_feedback_response(user_id, feedback_text):
    """Handle feedback submission"""
    logger.info(f"Handling feedback response for user {user_id}")
    
    # In a real implementation, store feedback in a database
    logger.info(f"Feedback from user {user_id}: {feedback_text}")
    
    # Thank the user
    send_text_message(
        user_id,
        "Thank you for your feedback! We appreciate you taking the time to share your thoughts with us."
    )
    
    # Ask for a rating
    buttons = [
        {"type": "reply", "reply": {"id": "rating_5", "title": "⭐⭐⭐⭐⭐ (5/5)"}},
        {"type": "reply", "reply": {"id": "rating_4", "title": "⭐⭐⭐⭐ (4/5)"}},
        {"type": "reply", "reply": {"id": "rating_3", "title": "⭐⭐⭐ (3/5)"}}
    ]
    
    send_button_message(
        user_id,
        "Rate Your Experience",
        "How would you rate your shopping experience with us?",
        buttons
    )
    
    # Reset action
    set_current_action(user_id, None)
    
    return True

def handle_rating_submission(user_id, rating):
    """Handle customer rating submission"""
    logger.info(f"Handling rating submission for user {user_id}, rating={rating}")
    
    # In a real implementation, store rating in a database
    
    # Thank the user
    send_text_message(
        user_id,
        f"Thank you for your {rating}/5 rating! We're {rating >= 4 and 'thrilled to hear you had a great experience' or 'always working to improve our service'}."
    )
    
    # Offer to continue shopping
    buttons = [
        {"type": "reply", "reply": {"id": "browse", "title": "Continue Shopping"}},
        {"type": "reply", "reply": {"id": "support", "title": "More Help"}}
    ]
    
    send_button_message(
        user_id,
        "Thank You",
        "What would you like to do next?",
        buttons
    )
    
    return True

def handle_cancel(user_id):
    """Handle cancel intent (cancel current action)"""
    logger.info(f"Handling cancel for user {user_id}")
    
    # Reset current action
    set_current_action(user_id, None)
    
    send_text_message(
        user_id,
        "I've reset your current action. How else can I help you today?"
    )
    
    # Show main menu
    buttons = [
        {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}},
        {"type": "reply", "reply": {"id": "view_cart", "title": "View Cart"}},
        {"type": "reply", "reply": {"id": "support", "title": "Get Help"}}
    ]
    
    send_button_message(
        user_id,
        "Main Menu",
        "What would you like to do?",
        buttons
    )
    
    return True