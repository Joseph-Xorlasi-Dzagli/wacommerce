import json
from flask import Flask, request, jsonify
from datetime import datetime

# Import configuration
from config import VERIFY_TOKEN, DEBUG, PORT, logger

# Import utilities
from utils.ngrok import start_ngrok_tunnel, stop_ngrok

# Import business context services
from services.business_context import BusinessContextService, BusinessContextError
from services.database import database_service

# Import services
from services.catalog import initialize_catalog
from services.intent import process_intent

# Import session and data management
from models.session import (
    update_session_history,
    get_current_action,
    set_current_action,
    set_user_name
)

# Import handlers
from handlers.greeting import handle_greeting
from handlers.browse import (
    handle_browse_catalog, 
    handle_browse_product,
    handle_product_details,
    handle_featured_products,
    handle_see_more_like_this,
    handle_view_product_options
)
from handlers.cart import (
    handle_add_to_cart,
    handle_view_cart,
    handle_remove_from_cart,
    handle_clear_cart,
    handle_awaiting_product_for_cart
)
from handlers.checkout import (
    handle_checkout,
    handle_confirm_checkout,
    handle_payment_selection,
    handle_shipping_options,
    handle_shipping_address,
    handle_momo_network_selection,
    handle_momo_number_submission,
    handle_existing_momo_payment,
    handle_new_momo_request,
    handle_location_message,
    handle_proceed_with_available,
    handle_cancel_inventory_order
)
from handlers.order import (
    handle_order_status,
    handle_order_message
)
from handlers.support import (
    handle_support,
    handle_support_faq,
    handle_support_shipping,
    handle_support_returns,
    handle_support_contact,
    handle_feedback_response
)

from services.messenger import send_button_message, send_text_message

# Initialize Flask app
app = Flask(__name__)

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """Verify webhook for WhatsApp Business API"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("Webhook verified successfully")
            return challenge, 200
        else:
            logger.warning("Webhook verification failed")
            return "Verification failed", 403
    
    return "Hello world", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming WhatsApp messages with business context"""
    try:
        data = request.get_json()
        logger.debug(f"Received webhook data: {json.dumps(data)}")
        
        # Extract business context from webhook
        business_context = BusinessContextService.extract_business_context(data)
        
        if not business_context:
            logger.error("Failed to extract business context from webhook")
            return "Business context error", 400
        
        # Validate business context
        is_valid, error_message = BusinessContextService.validate_business_context(business_context)
        if not is_valid:
            logger.error(f"Invalid business context: {error_message}")
            return f"Invalid business context: {error_message}", 400
        
        # Log business context summary
        context_summary = BusinessContextService.get_business_context_summary(business_context)
        logger.info(f"Processing webhook for business: {context_summary}")
        
        # Process messages with business context
        if data.get("object") and data.get("entry"):
            for entry in data["entry"]:
                for change in entry.get("changes", []):
                    if change.get("field") == "messages":
                        value = change.get("value", {})
                        
                        messages = value.get("messages", [])
                        contacts = value.get("contacts", [])
                        
                        logger.info(f"Extracted {len(messages)} messages for business {business_context.business_id}")
                        
                        if messages and len(messages) > 0:
                            process_messages_with_context(messages, contacts, value, business_context)
        
        return "OK", 200
    except BusinessContextError as e:
        logger.error(f"Business context error: {str(e)}")
        return f"Business context error: {str(e)}", 400
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return "Error", 500

def process_messages_with_context(messages, contacts, metadata, business_context):
    """Process messages with business context"""
    # Extract contact information if available
    contact_info = {}
    if contacts and len(contacts) > 0:
        profile = contacts[0].get("profile", {})
        if "name" in profile:
            contact_info["name"] = profile["name"]
    
    for message in messages:
        user_id = message.get("from")
        
        if not user_id:
            logger.warning("Message received without user ID")
            continue
        
        # Create or update customer record
        if database_service:
            customer_id = database_service.get_or_create_customer(
                business_id=business_context.business_id,
                whatsapp_number=user_id,
                name=contact_info.get("name")
            )
            
            # Log analytics event
            database_service.log_whatsapp_event(
                business_id=business_context.business_id,
                event_type='message_received',
                user_id=user_id,
                metadata={
                    'message_type': message.get("type"),
                    'customer_id': customer_id
                }
            )
        
        # Update user name if available
        if contact_info and "name" in contact_info:
            set_user_name(business_context.business_id, user_id, contact_info["name"])
        
        message_type = message.get("type")
                
        if message_type == "text":
            handle_text_message_with_context(user_id, message, business_context)
        elif message_type == "interactive":
            handle_interactive_message_with_context(user_id, message, business_context)
        elif message_type == "button":
            handle_button_message_with_context(user_id, message, business_context)
        elif message_type == "location":
            handle_location_message_with_context(user_id, message, business_context)
        elif message_type == "order":
            handle_order_message_with_context(user_id, message, business_context)
        else:
            logger.info(f"Received unsupported message type: {message_type}")
            send_text_message_with_context(business_context, user_id, 
                "I received your message but I can only process text, buttons, orders, or location right now.")


def handle_text_message_with_context(user_id, message, business_context):
    """Handle a text message from the user with business context"""
    message_body = message.get("text", {}).get("body", "")
    logger.info(f"Received text message from {user_id} for business {business_context.business_id}: {message_body}")
    
    # Update user session history
    update_session_history(business_context.business_id, user_id, "user", message_body)
    
    # Check if we're waiting for a specific response
    current_action = get_current_action(business_context.business_id, user_id)
    
    if current_action == "awaiting_product_query" or current_action == "awaiting_product_for_cart":
        handle_awaiting_product_for_cart(business_context, user_id, message_body)
    elif current_action == "awaiting_shipping_address" or current_action == "awaiting_shipping_address_or_location":
        handle_shipping_address(business_context, user_id, message_body)
    elif current_action == "awaiting_momo_number":
        handle_momo_number_submission(business_context, user_id, message_body)
    elif current_action == "awaiting_feedback":
        handle_feedback_response(business_context, user_id, message_body)
    elif current_action == "awaiting_inventory_decision":
        # Handle inventory decision
        message_lower = message_body.lower()
        
        if any(word in message_lower for word in ["proceed", "continue", "yes", "accept", "available"]):
            handle_proceed_with_available(business_context, user_id)
        elif any(word in message_lower for word in ["cancel", "no", "stop", "abort"]):
            handle_cancel_inventory_order(business_context, user_id)
        else:
            # Unclear response - ask for clarification
            buttons = [
                {"type": "reply", "reply": {"id": "proceed_with_available", "title": "Proceed to Checkout"}},
                {"type": "reply", "reply": {"id": "cancel_inventory_order", "title": "Cancel Order"}}
            ]
            
            send_button_message_with_context(
                business_context,
                user_id,
                "Please Choose",
                "I didn't understand your response. Would you like to proceed with the available items or cancel your order?",
                buttons
            )
    else:
        # Process user intent
        intent_data = process_intent(message_body, business_context.business_id, user_id)
        logger.info(f"Detected intent: {intent_data}")
        
        # Handle based on intent
        intent = intent_data.get("intent", "unknown")
        
        if intent == "greeting":
            handle_greeting(business_context, user_id)
        elif intent == "browse_catalog":
            handle_browse_catalog(business_context, user_id)
        elif intent == "browse_product":
            product_query = intent_data.get("entities", {}).get("product", "")
            handle_browse_product(business_context, user_id, product_query)
        elif intent == "product_info":
            product_query = intent_data.get("entities", {}).get("product", "")
            handle_browse_product(business_context, user_id, product_query)
        elif intent == "add_to_cart":
            product_query = intent_data.get("entities", {}).get("product", "")
            if product_query:
                handle_browse_product(business_context, user_id, product_query)
            else:
                send_text_message_with_context(business_context, user_id, "What product would you like to add to your cart?")
        elif intent == "view_cart":
            handle_view_cart(business_context, user_id)
        elif intent == "checkout":
            handle_checkout(business_context, user_id)
        elif intent == "order_status":
            handle_order_status(business_context, user_id)
        elif intent == "support":
            handle_support(business_context, user_id)
        elif intent == "cancel":
            set_current_action(business_context.business_id, user_id, None)
            send_text_message_with_context(business_context, user_id, "I've reset your current action. How can I help you today?")
            
            buttons = [
                {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}},
                {"type": "reply", "reply": {"id": "support", "title": "Get Help"}}
            ]
            
            send_button_message_with_context(business_context, user_id, "Main Menu", "What would you like to do?", buttons)
        else:
            # Unknown intent - use business-specific greeting
            try:
                greeting_msg = business_context.get_greeting_message()
                send_text_message_with_context(business_context, user_id, f"I'm not sure I understand. {greeting_msg}")
            except AttributeError as e:
                logger.error(f"Error getting greeting message: {str(e)}")
                # Fallback message
                send_text_message_with_context(business_context, user_id, "I'm not sure I understand. How can I help you today?")
            
            buttons = [
                {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}},
                {"type": "reply", "reply": {"id": "support", "title": "Get Help"}}
            ]
            
            send_button_message_with_context(business_context, user_id, "Menu Options", "Please select from the following options:", buttons)

def handle_interactive_message_with_context(user_id, message, business_context):
    """Handle interactive messages (button clicks, list selections) with business context"""
    interactive = message.get("interactive", {})
    interactive_type = interactive.get("type")
    
    if interactive_type == "button_reply":
        button_id = interactive.get("button_reply", {}).get("id", "")
        button_text = interactive.get("button_reply", {}).get("title", "")
        logger.info(f"Received button click from {user_id} for business {business_context.business_id}: {button_id} ({button_text})")
        
        update_session_history(business_context.business_id, user_id, "user", f"Clicked: {button_text}")
        handle_interaction_with_context(user_id, button_id, business_context)
        
    elif interactive_type == "list_reply":
        list_id = interactive.get("list_reply", {}).get("id", "")
        list_title = interactive.get("list_reply", {}).get("title", "")
        logger.info(f"Received list selection from {user_id} for business {business_context.business_id}: {list_id} ({list_title})")
        
        update_session_history(business_context.business_id, user_id, "user", f"Selected: {list_title}")
        handle_interaction_with_context(user_id, list_id, business_context)
    else:
        logger.warning(f"Received unsupported interactive type: {interactive_type}")
        send_text_message_with_context(business_context, user_id, "I received your interactive message but couldn't process it. Please try again.")

def handle_button_message_with_context(user_id, message, business_context):
    """Handle button messages from the user with business context"""
    button = message.get("button", {})
    payload = button.get("payload", "")
    button_text = button.get("text", "")
    logger.info(f"Received button message from {user_id} for business {business_context.business_id}: {payload} ({button_text})")

    update_session_history(business_context.business_id, user_id, "user", f"Clicked: {button_text}")
    handle_interaction_with_context(user_id, payload, business_context)

def handle_location_message_with_context(user_id, message, business_context):
    """Handle location messages with business context"""
    handle_location_message(business_context, user_id, message)

def handle_order_message_with_context(user_id, message, business_context):
    """Handle order messages with business context"""
    handle_order_message(business_context, user_id, message)

def handle_interaction_with_context(user_id, interaction_id, business_context):
    """Handle various interaction types with business context"""
    try:
        # Direct interaction mappings
        if interaction_id == "browse":
            handle_browse_catalog(business_context, user_id)
        elif interaction_id == "featured":
            handle_featured_products(business_context, user_id)
        elif interaction_id == "view_cart":
            handle_view_cart(business_context, user_id)
        elif interaction_id == "clear_cart":
            handle_clear_cart(business_context, user_id)
        elif interaction_id == "checkout":
            handle_checkout(business_context, user_id)
        elif interaction_id == "confirm_checkout":
            handle_confirm_checkout(business_context, user_id)
        elif interaction_id == "proceed_with_available":
            handle_proceed_with_available(business_context, user_id)
        elif interaction_id == "cancel_inventory_order":
            handle_cancel_inventory_order(business_context, user_id)
        elif interaction_id == "payment_new_momo":
            from models.session import get_last_context
            context = get_last_context(business_context.business_id, user_id)
            order_id = context.get("order_id", "") if context else ""
            handle_new_momo_request(business_context, user_id, order_id)
        elif interaction_id == "payment_cod":
            handle_payment_selection(business_context, user_id, "payment_cod")
        elif interaction_id == "support":
            handle_support(business_context, user_id)
        elif interaction_id == "support_faq":
            handle_support_faq(business_context, user_id)
        elif interaction_id == "support_shipping":
            handle_support_shipping(business_context, user_id)
        elif interaction_id == "support_returns":
            handle_support_returns(business_context, user_id)
        elif interaction_id == "support_contact":
            handle_support_contact(business_context, user_id)
        
        # Pattern-based interactions
        elif interaction_id.startswith("cat_"):
            category = interaction_id[4:]
            handle_browse_catalog(business_context, user_id, category)
        elif interaction_id.startswith("view_options_"):
            product_id = interaction_id[13:]
            handle_view_product_options(business_context, user_id, product_id)
        elif interaction_id.startswith("product_"):
            product_id = interaction_id[8:]
            handle_product_details(business_context, user_id, product_id)
        elif interaction_id.startswith("add_"):
            product_id = interaction_id[4:]
            handle_add_to_cart(business_context, user_id, product_id)
        elif interaction_id.startswith("remove_"):
            product_id = interaction_id[7:]
            handle_remove_from_cart(business_context, user_id, product_id)
        elif interaction_id.startswith("more_"):
            parts = interaction_id[5:].split("_")
            if len(parts) == 2:
                category, offset = parts
                handle_see_more_like_this(business_context, user_id, category, int(offset))
        
        # Payment handling - existing saved accounts
        elif interaction_id.startswith("payment_momo_"):
            account_id = interaction_id[13:]
            from models.session import get_last_context
            context = get_last_context(business_context.business_id, user_id)
            order_id = context.get("order_id", "") if context else ""
            handle_existing_momo_payment(business_context, user_id, order_id, account_id)
        
        # Payment handling - network selection for new accounts
        elif interaction_id.startswith("momo_network_"):
            network = interaction_id[13:]
            handle_momo_network_selection(business_context, user_id, network)
        
        # Shipping handling - new address
        elif interaction_id == "shipping_new_address":
            from handlers.checkout import handle_shipping_selection
            handle_shipping_selection(business_context, user_id, "shipping_new_address")
        
        # Shipping handling - location sharing
        elif interaction_id == "shipping_location":
            from handlers.checkout import handle_shipping_selection
            handle_shipping_selection(business_context, user_id, "shipping_location")
        
        # Shipping handling - existing saved addresses
        elif interaction_id.startswith("shipping_address_"):
            address_id = interaction_id[17:]
            from models.session import get_last_context
            context = get_last_context(business_context.business_id, user_id)
            order_id = context.get("order_id", "") if context else ""
            from handlers.checkout import handle_existing_address_selection
            handle_existing_address_selection(business_context, user_id, order_id, address_id)
        
        # Order management
        elif interaction_id.startswith("order_"):
            order_id = interaction_id[6:]
            handle_order_status(business_context, user_id, order_id)
        elif interaction_id.startswith("track_"):
            order_id = interaction_id[6:]
            from handlers.order import handle_track_order
            handle_track_order(business_context, user_id, order_id)
        
        # Rating and feedback
        elif interaction_id.startswith("rating_"):
            rating = int(interaction_id[7:])
            from handlers.support import handle_rating_submission
            handle_rating_submission(business_context, user_id, rating)
        
        # Support and help
        elif interaction_id == "connect_agent":
            from handlers.support import handle_connect_agent
            handle_connect_agent(business_context, user_id)
        
        # Cancel actions
        elif interaction_id == "cancel":
            from handlers.support import handle_cancel
            handle_cancel(business_context, user_id)
        
        # Save location as address
        elif interaction_id == "save_location_address":
            send_text_message_with_context(
                business_context,
                user_id,
                "To save this location, please provide a name for this address (e.g., 'Home', 'Work', etc.)"
            )
            set_current_action(business_context.business_id, user_id, "awaiting_location_address_name")
        
        # Address saving decisions
        elif interaction_id.startswith("save_address_"):
            order_id = interaction_id[13:]
            from handlers.checkout import handle_save_address_decision
            handle_save_address_decision(business_context, user_id, "save", order_id)
        elif interaction_id.startswith("no_save_address_"):
            order_id = interaction_id[16:]
            from handlers.checkout import handle_save_address_decision  
            handle_save_address_decision(business_context, user_id, "no_save", order_id)
        
        # Order cancellation
        elif interaction_id.startswith("cancel_"):
            order_id = interaction_id[7:]
            from handlers.order import handle_cancel_order
            handle_cancel_order(business_context, user_id, order_id)
        elif interaction_id.startswith("confirm_cancel_"):
            order_id = interaction_id[15:]
            from handlers.order import handle_confirm_cancel_order
            handle_confirm_cancel_order(business_context, user_id, order_id)
        
        # Search again
        elif interaction_id == "search_again":
            send_text_message_with_context(business_context, user_id, "What product are you looking for?")
            set_current_action(business_context.business_id, user_id, "awaiting_product_query")
        
        # Fallback for unhandled interactions
        else:
            logger.warning(f"No handler found for interaction ID: {interaction_id}")
            send_text_message_with_context(business_context, user_id, "Sorry, I couldn't process that selection. Please try again.")
            
            # Offer main menu options
            buttons = [
                {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}},
                {"type": "reply", "reply": {"id": "support", "title": "Get Help"}}
            ]
            
            send_button_message_with_context(
                business_context,
                user_id,
                "Menu Options",
                "Please select from the following options:",
                buttons
            )
            
    except Exception as e:
        logger.error(f"Error handling interaction {interaction_id} for business {business_context.business_id}: {str(e)}")
        send_text_message_with_context(business_context, user_id, "Sorry, there was an error processing your request. Please try again.")
        
        # Offer main menu options as fallback
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}},
            {"type": "reply", "reply": {"id": "support", "title": "Get Help"}}
        ]
        
        send_button_message_with_context(
            business_context,
            user_id,
            "Error Recovery",
            "Something went wrong. What would you like to do?",
            buttons
        )

# Helper functions for business-aware messaging
def send_text_message_with_context(business_context, recipient_id, text):
    """Send text message with business context"""
    from services.messenger import send_whatsapp_message_with_context
    return send_whatsapp_message_with_context(business_context, recipient_id, {
        "type": "text",
        "text": {"body": text}
    })

def send_button_message_with_context(business_context, recipient_id, header_text, body_text, buttons):
    """Send button message with business context"""
    from services.messenger import send_whatsapp_message_with_context
    return send_whatsapp_message_with_context(business_context, recipient_id, {
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {
                "type": "text",
                "text": header_text
            },
            "body": {
                "text": body_text
            },
            "action": {
                "buttons": buttons
            }
        }
    })

@app.route("/", methods=["GET"])
def home():
    """Home route for checking if service is running"""
    return "WhatsApp E-commerce Bot is running!"

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint with database status"""
    try:
        # Test database connection
        db_status = database_service.test_connection() if database_service else False
        
        return jsonify({
            "status": "healthy" if db_status else "degraded",
            "database": "connected" if db_status else "disconnected",
            "timestamp": datetime.now().isoformat()
        }), 200 if db_status else 503
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

def setup_app():
    """Initialize app components"""
    logger.info("Setting up application...")
    
    # Test database connection
    if database_service:
        if database_service.test_connection():
            logger.info("Database connection successful")
        else:
            logger.error("Database connection failed")
    else:
        logger.error("Database service not available")
    
    # Initialize product catalog (this will need updating in Phase 3)
    # initialize_catalog()
    
    logger.info("Application setup complete")

def start_app(use_ngrok=False):
    """Start the Flask application"""
    setup_app()
    
    webhook_url = None
    if use_ngrok:
        webhook_url = start_ngrok_tunnel(PORT)
    
    try:
        logger.info(f"Starting Flask app on port {PORT}")
        app.run(debug=DEBUG, port=PORT, host='0.0.0.0')
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        if use_ngrok:
            stop_ngrok()
    except Exception as e:
        logger.error(f"Error running app: {str(e)}")
        if use_ngrok:
            stop_ngrok()

if __name__ == "__main__":
    start_app()
    start_app()