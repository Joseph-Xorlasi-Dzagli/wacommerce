from services.messenger import send_text_message, send_button_message, send_list_message
from models.session import set_current_action
from utils.logger import get_logger

logger = get_logger(__name__)

def handle_support(business_context, user_id):
    """Handle customer support intent with business context"""
    logger.info(f"Handling support for user {user_id}, business={business_context.get('business_id')}")
    
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
        business_context,
        user_id,
        "Customer Support",
        "How can we help you today?",
        "Select an Option",
        sections
    )
    
    return True

def handle_support_faq(business_context, user_id):
    """Handle FAQ support option with business context"""
    logger.info(f"Handling FAQ for user {user_id}, business={business_context.get('business_id')}")
    
    # Get business-specific FAQ content
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    # Default FAQ content
    faq_text = (
        "*Frequently Asked Questions*\n\n"
        "*How long does shipping take?*\n"
        "Standard shipping takes 3-5 business days. Express shipping takes 1-2 business days.\n\n"
        
        "*Do you ship internationally?*\n"
        "Yes, we ship to most countries worldwide. International shipping typically takes 7-14 business days.\n\n"
        
        "*How can I track my order?*\n"
        "You'll receive a tracking number via WhatsApp once your order ships. You can also check your order status by sending 'order status'.\n\n"
        
        "*What payment methods do you accept?*\n"
        "We accept mobile money (MTN, Vodafone, AirtelTigo) and cash on delivery.\n\n"
        
        "*How do I return an item?*\n"
        "Contact our support team within 30 days of receiving your order. We'll guide you through the return process."
    )
    
    # Try to get business-specific FAQ content
    if db and business_id:
        try:
            # Check for business-specific FAQ content in business_settings
            settings_ref = db.collection('business_settings').document(business_id)
            settings_doc = settings_ref.get()
            
            if settings_doc.exists:
                settings_data = settings_doc.to_dict()
                custom_faq = settings_data.get('support', {}).get('faq_content')
                if custom_faq:
                    faq_text = custom_faq
                    
        except Exception as e:
            logger.warning(f"Could not fetch business FAQ for {business_id}: {str(e)}")
    
    send_text_message(business_context, user_id, faq_text)
    
    # Offer additional help
    buttons = [
        {"type": "reply", "reply": {"id": "support", "title": "More Help Options"}},
        {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
    ]
    
    send_button_message(
        business_context,
        user_id,
        "More Questions?",
        "Can we help with anything else?",
        buttons
    )
    
    return True

def handle_support_shipping(business_context, user_id):
    """Handle shipping information support option with business context"""
    logger.info(f"Handling shipping info for user {user_id}, business={business_context.get('business_id')}")
    
    # Get business-specific shipping policies
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    # Default shipping text
    shipping_text = (
        "*Shipping Information*\n\n"
        "*Standard Delivery (Free)*\n"
        "• Delivery in 3-5 business days\n"
        "• Available for all domestic orders\n"
        "• Free for orders over GHS50\n\n"
        
        "*Express Delivery (GHS9.99)*\n"
        "• Delivery in 1-2 business days\n"
        "• Available for orders placed before 2PM\n"
        "• Includes weekend delivery\n\n"
        
        "*International Shipping*\n"
        "• Delivery in 7-14 business days\n"
        "• Shipping costs vary by destination\n"
        "• Customs fees may apply\n\n"
        
        "*Store Pickup (Free)*\n"
        "• Available for collection same day if ordered before 3PM\n"
        "• Please bring ID and order number"
    )
    
    # Try to get business-specific shipping info
    if db and business_id:
        try:
            settings_ref = db.collection('business_settings').document(business_id)
            settings_doc = settings_ref.get()
            
            if settings_doc.exists:
                settings_data = settings_doc.to_dict()
                checkout_settings = settings_data.get('checkout', {})
                shipping_methods = checkout_settings.get('shipping_methods', [])
                
                if shipping_methods:
                    # Build custom shipping text from business settings
                    custom_shipping_text = "*Shipping Information*\n\n"
                    for method in shipping_methods:
                        method_name = method.get('name', 'Standard')
                        method_cost = method.get('cost', 'Free')
                        method_time = method.get('delivery_time', '3-5 business days')
                        custom_shipping_text += f"*{method_name}* ({method_cost})\n"
                        custom_shipping_text += f"• Delivery in {method_time}\n\n"
                    
                    shipping_text = custom_shipping_text
                    
        except Exception as e:
            logger.warning(f"Could not fetch business shipping info for {business_id}: {str(e)}")
    
    send_text_message(business_context, user_id, shipping_text)
    
    # Offer additional help
    buttons = [
        {"type": "reply", "reply": {"id": "support", "title": "More Help Options"}},
        {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
    ]
    
    send_button_message(
        business_context,
        user_id,
        "More Questions?",
        "Can we help with anything else?",
        buttons
    )
    
    return True

def handle_support_returns(business_context, user_id):
    """Handle returns and refunds support option with business context"""
    logger.info(f"Handling returns info for user {user_id}, business={business_context.get('business_id')}")
    
    # Default returns text
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
        "• Sale items may have different return conditions"
    )
    
    send_text_message(business_context, user_id, returns_text)
    
    # Offer additional help
    buttons = [
        {"type": "reply", "reply": {"id": "support", "title": "More Help Options"}},
        {"type": "reply", "reply": {"id": "support_contact", "title": "Contact Support"}}
    ]
    
    send_button_message(
        business_context,
        user_id,
        "Need to Return Something?",
        "Our support team can help with your return.",
        buttons
    )
    
    return True

def handle_support_contact(business_context, user_id):
    """Handle contact support team option with business context"""
    logger.info(f"Handling contact support for user {user_id}, business={business_context.get('business_id')}")
    
    # Get business contact information
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    # Default contact text
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
        
        "You can also continue this conversation for support. How can we help you today?"
    )
    
    # Try to get business-specific contact info
    if db and business_id:
        try:
            # Get business contact details
            business_ref = db.collection('businesses').document(business_id)
            business_doc = business_ref.get()
            
            if business_doc.exists:
                business_data = business_doc.to_dict()
                business_name = business_data.get('name', 'Our Team')
                
                # Get business contacts
                contacts_ref = db.collection('business_contacts').document(business_id)
                contacts_doc = contacts_ref.get()
                
                if contacts_doc.exists:
                    contacts_data = contacts_doc.to_dict()
                    email = contacts_data.get('email', 'support@example.com')
                    phone = contacts_data.get('phone', '1-800-123-4567')
                    whatsapp = contacts_data.get('whatsapp', '')
                    
                    # Build custom contact text
                    contact_text = (
                        f"*Contact {business_name} Support*\n\n"
                        "Our customer service team is here to help!\n\n"
                        
                        "*Contact Options:*\n"
                        f"• Email: {email}\n"
                        f"• Phone: {phone}\n"
                    )
                    
                    if whatsapp:
                        contact_text += f"• WhatsApp: {whatsapp}\n"
                    
                    contact_text += "\nYou can also continue this conversation for support. How can we help you today?"
                    
        except Exception as e:
            logger.warning(f"Could not fetch business contact info for {business_id}: {str(e)}")
    
    send_text_message(business_context, user_id, contact_text)
    
    # Offer to continue with feedback
    buttons = [
        {"type": "reply", "reply": {"id": "feedback", "title": "Leave Feedback"}},
        {"type": "reply", "reply": {"id": "browse", "title": "Continue Shopping"}}
    ]
    
    send_button_message(
        business_context,
        user_id,
        "Support Available",
        "Is there anything specific we can help you with?",
        buttons
    )
    
    return True

def handle_feedback(business_context, user_id):
    """Handle customer feedback intent with business context"""
    logger.info(f"Handling feedback for user {user_id}, business={business_context.get('business_id')}")
    
    send_text_message(
        business_context,
        user_id,
        "We value your feedback! Please share your thoughts, suggestions, or experiences with our products and service."
    )
    
    # Set action
    set_current_action(user_id, "awaiting_feedback")
    
    return True

def handle_feedback_response(business_context, user_id, feedback_text):
    """Handle feedback submission with business context"""
    logger.info(f"Handling feedback response for user {user_id}, business={business_context.get('business_id')}")
    
    # Store feedback in Firebase
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if db and business_id:
        try:
            from firebase_admin import firestore
            feedback_data = {
                'business_id': business_id,
                'user_id': user_id,
                'feedback_text': feedback_text,
                'type': 'general_feedback',
                'status': 'new',
                'created_at': firestore.SERVER_TIMESTAMP
            }
            db.collection('customer_feedback').add(feedback_data)
            logger.info(f"Stored feedback from user {user_id} for business {business_id}")
        except Exception as e:
            logger.error(f"Error storing feedback: {str(e)}")
    
    # Thank the user
    send_text_message(
        business_context,
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
        business_context,
        user_id,
        "Rate Your Experience",
        "How would you rate your shopping experience with us?",
        buttons
    )
    
    # Reset action
    set_current_action(user_id, None)
    
    return True

def handle_rating_submission(business_context, user_id, rating):
    """Handle customer rating submission with business context"""
    logger.info(f"Handling rating submission for user {user_id}, rating={rating}, business={business_context.get('business_id')}")
    
    # Store rating in Firebase
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if db and business_id:
        try:
            from firebase_admin import firestore
            rating_data = {
                'business_id': business_id,
                'user_id': user_id,
                'rating': rating,
                'type': 'experience_rating',
                'created_at': firestore.SERVER_TIMESTAMP
            }
            db.collection('customer_ratings').add(rating_data)
            logger.info(f"Stored rating {rating} from user {user_id} for business {business_id}")
        except Exception as e:
            logger.error(f"Error storing rating: {str(e)}")
    
    # Thank the user
    response_message = f"Thank you for your {rating}/5 rating! "
    if rating >= 4:
        response_message += "We're thrilled to hear you had a great experience with us!"
    else:
        response_message += "We're always working to improve our service and appreciate your honest feedback."
    
    send_text_message(business_context, user_id, response_message)
    
    # Offer to continue shopping
    buttons = [
        {"type": "reply", "reply": {"id": "browse", "title": "Continue Shopping"}},
        {"type": "reply", "reply": {"id": "support", "title": "More Help"}}
    ]
    
    send_button_message(
        business_context,
        user_id,
        "Thank You",
        "What would you like to do next?",
        buttons
    )
    
    return True

def handle_cancel(business_context, user_id):
    """Handle cancel intent (cancel current action) with business context"""
    logger.info(f"Handling cancel for user {user_id}, business={business_context.get('business_id')}")
    
    # Reset current action
    set_current_action(user_id, None)
    
    send_text_message(
        business_context,
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
        business_context,
        user_id,
        "Main Menu",
        "What would you like to do?",
        buttons
    )
    
    return True