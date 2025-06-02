import json
import re
from flask import Flask, request, jsonify

# Import configuration
from config import VERIFY_TOKEN, DEBUG, PORT, logger

# Import utilities
from utils.ngrok import start_ngrok_tunnel, stop_ngrok

# Import services
from services.catalog import initialize_catalog
from services.intent import process_intent, analyze_message_content

# Import session and data management
from models.session import (
    update_session_history,
    get_current_action,
    set_current_action
)

# Import handlers
from handlers import (
    get_handler_for_intent,
    get_handler_for_interaction,
    handle_greeting,
    handle_awaiting_product_for_cart,
    handle_shipping_address,
    handle_feedback_response, 
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
    """Handle incoming WhatsApp messages"""
    try:
        data = request.get_json()
        logger.debug(f"Received webhook data: {json.dumps(data)}")
        
        if data.get("object") and data.get("entry"):
            for entry in data["entry"]:
                for change in entry.get("changes", []):
                    if change.get("field") == "messages":
                        value = change.get("value", {})
                        
                        # This is where the messages should be
                        messages = value.get("messages", [])
                        contacts = value.get("contacts", [])
                        
                        # Debug logging
                        logger.info(f"Extracted messages: {json.dumps(messages)}")
                        logger.info(f"Extracted contacts: {json.dumps(contacts)}")
                        
                        if messages and len(messages) > 0:
                            # Process the messages with contacts info
                            process_messages(messages, contacts, value)
        
        return "OK", 200
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return "Error", 500

def process_messages(messages, contacts, metadata):
    """Process messages with contact information"""
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
        
        # Update user name if available
        if contact_info and "name" in contact_info:
            from models.session import set_user_name
            set_user_name(user_id, contact_info["name"])
        
        message_type = message.get("type")
                
        if message_type == "text":
            # Handle text message
            handle_text_message(user_id, message)
        
        elif message_type == "interactive":
            # Handle interactive message (button/list response)
            handle_interactive_message(user_id, message)
        
        elif message_type == "button":
            # Handle interactive message (button/list response)
            handle_button_message(user_id, message)
        
        elif message_type == "location":
            # Handle location message
            from handlers.checkout import handle_location_message 
            handle_location_message(user_id, message)
        
        elif message_type == "image":
            # Handle image message
            handle_image_message(user_id, message)
            
        elif message_type == "location":
            # Handle location message
            from handlers.checkout import handle_location_message
            handle_location_message(user_id, message)
        
        elif message_type == "order":
            # Handle order message
            handle_order_message(user_id, message)
        
        else:
            # Handle other message types
            logger.info(f"Received unsupported message type: {message_type}")
            from services.messenger import send_text_message
            send_text_message(user_id, "I received your message but I can only process text, buttons, orders, or location right now.")


def handle_text_message(user_id, message):
    """Handle a text message from the user"""
    message_body = message.get("text", {}).get("body", "")
    logger.info(f"Received text message from {user_id}: {message_body}")
    
    # Update user session history
    update_session_history(user_id, "user", message_body)
    
    # Check if we're waiting for a specific response
    current_action = get_current_action(user_id)
    
    if current_action == "awaiting_product_query" or current_action == "awaiting_product_for_cart":
        # User is providing a product query
        handle_awaiting_product_for_cart(user_id, message_body)
    
    elif current_action == "awaiting_shipping_address":
        # User is providing a shipping address
        handle_shipping_address(user_id, message_body)
    
    elif current_action == "awaiting_shipping_address_or_location":
        # User chose to manually enter an address instead of sharing location
        from handlers.checkout import handle_message_after_location_request
        handle_message_after_location_request(user_id, message_body)
    
    elif current_action == "awaiting_momo_number":
        # User is providing a mobile money number
        from handlers.checkout import handle_momo_number_submission
        handle_momo_number_submission(user_id, message_body)
    
    elif current_action == "awaiting_feedback":
        # User is providing feedback
        handle_feedback_response(user_id, message_body)
    
    elif current_action == "awaiting_agent":
        # User is chatting with an agent (simulated)
        from services.messenger import send_text_message
        send_text_message(
            user_id,
            "👨‍💼 *Agent Sarah:* Thank you for your message. Is there anything else I can help you with today?"
        )
    
    else:
        # Process user intent
        intent_data = process_intent(message_body, user_id)
        logger.info(f"Detected intent: {intent_data}")
        
        # Get the appropriate handler for this intent
        intent = intent_data.get("intent", "unknown")
        handler = get_handler_for_intent(intent)
        
        if handler:
            # We have a handler for this intent
            if intent == "browse_product" and "entities" in intent_data and "product" in intent_data["entities"]:
                # For product browsing, pass the product query
                handler(user_id, intent_data["entities"]["product"])
            elif intent == "add_to_cart" and "entities" in intent_data and "product" in intent_data["entities"]:
                # For add to cart, pass product and quantity
                quantity = intent_data.get("entities", {}).get("quantity", 1)
                handler(user_id, intent_data["entities"]["product"], quantity)
            elif intent == "product_info" and "entities" in intent_data and "product" in intent_data["entities"]:
                # For product info, pass the product
                handler(user_id, intent_data["entities"]["product"])
            elif intent == "order_status" and "entities" in intent_data and "order_id" in intent_data["entities"]:
                # For order status, pass the order ID
                handler(user_id, intent_data["entities"]["order_id"])
            
            else:
                # Call the handler with default parameters
                handler(user_id)
        else:
            # No specific handler for this intent
            if intent == "unknown":
                # Try a simple pattern-based intent detection as fallback
                fallback_intent = analyze_message_content(message_body)
                if fallback_intent["intent"] != "unknown":
                    # We found a pattern match
                    fallback_handler = get_handler_for_intent(fallback_intent["intent"])
                    if fallback_handler:
                        fallback_handler(user_id)
                        return
                
                # Truly unknown intent
                from services.messenger import send_text_message, send_button_message
                send_text_message(
                    user_id,
                    "I'm not sure I understand. How can I help you today?"
                )
                
                # Offer main menu options
                buttons = [
                    {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}},
                    {"type": "reply", "reply": {"id": "view_cart", "title": "View Cart"}},
                    {"type": "reply", "reply": {"id": "support", "title": "Get Help"}}
                ]
                
                send_button_message(
                    user_id,
                    "Menu Options",
                    "Please select from the following options:",
                    buttons
                )
                
                # If it seems like they're searching for something
                if any(word in message_body.lower() for word in ["find", "search", "looking", "where", "have", "sell"]):
                    send_text_message(
                        user_id,
                        "If you're looking for a specific product, please tell me what you're searching for. For example, 'I'm looking for shoes'."
                    )

def handle_interactive_message(user_id, message):
    """Handle interactive messages (button clicks, list selections)"""
    interactive = message.get("interactive", {})
    interactive_type = interactive.get("type")
    
    if interactive_type == "button_reply":
        # Handle button click
        button_id = interactive.get("button_reply", {}).get("id", "")
        button_text = interactive.get("button_reply", {}).get("title", "")
        logger.info(f"Received button click from {user_id}: {button_id} ({button_text})")
        
        # Update user session
        update_session_history(user_id, "user", f"Clicked: {button_text}")
        
        # Find handler for this button
        handler = get_handler_for_interaction(button_id)
        if handler:
            handler(user_id)
        else:
            logger.warning(f"No handler found for button ID: {button_id}")
            from services.messenger import send_text_message
            send_text_message(user_id, "Sorry, I couldn't process that selection. Please try again.")
    
    elif interactive_type == "list_reply":
        # Handle list selection
        list_id = interactive.get("list_reply", {}).get("id", "")
        list_title = interactive.get("list_reply", {}).get("title", "")
        logger.info(f"Received list selection from {user_id}: {list_id} ({list_title})")
        
        # Update user session
        update_session_history(user_id, "user", f"Selected: {list_title}")
        
        # Find handler for this list item
        handler = get_handler_for_interaction(list_id)
        if handler:
            handler(user_id)
        else:
            logger.warning(f"No handler found for list ID: {list_id}")
            from services.messenger import send_text_message
            send_text_message(user_id, "Sorry, I couldn't process that selection. Please try again.")
    
    else:
        logger.warning(f"Received unsupported interactive type: {interactive_type}")
        from services.messenger import send_text_message
        send_text_message(user_id, "I received your interactive message but couldn't process it. Please try again.")

def handle_location_message(user_id, message):
    """Handle location messages from the user"""
    location = message.get("location", {})
    latitude = location.get("latitude", 0)
    longitude = location.get("longitude", 0)
    
    logger.info(f"Received location from {user_id}: {latitude}, {longitude}")
    
    # Update user session history
    update_session_history(user_id, "user", f"Shared location: {latitude}, {longitude}")
    
    # Check if we're waiting for a location for delivery
    current_action = get_current_action(user_id)
    
    if current_action == "awaiting_shipping_address":
        # User shared location for shipping
        # In a real app, we would geocode this to get a proper address
        address = f"Coordinates: {latitude}, {longitude} (shared via WhatsApp location)"
        
        # Call shipping address handler
        handle_shipping_address(user_id, address)
    else:
        # User shared location but we weren't expecting it
        from services.messenger import send_text_message
        send_text_message(
            user_id,
            "Thank you for sharing your location. Is there something specific you're looking for near you?"
        )
        
        # Maybe offer store locations or something useful
        from services.messenger import send_button_message
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}},
            {"type": "reply", "reply": {"id": "support", "title": "Get Help"}}
        ]
        
        send_button_message(
            user_id,
            "How Can I Help?",
            "Is there something specific you're looking for?",
            buttons
        )


def handle_button_message(user_id, message):
    """Handle button messages from the user"""
    button = message.get("button", {})
    payload = button.get("payload", "")
    button_text = button.get("text", "")
    logger.info(f"Received button message from {user_id}: {payload} ({button_text})")

    # Update user session history
    update_session_history(user_id, "user", f"Clicked: {button_text}")

    # Find handler for this button payload
    handler = get_handler_for_interaction(payload)
    if handler:
        handler(user_id)
    else:
        send_text_message(user_id, "Sorry, I couldn't process that selection. Please try again.")

def handle_order_message(user_id, message):
    """Handle order messages from WhatsApp"""
    try:
        logger.info(f"Received order message from {user_id}")
        
        # Extract order data
        order_data = message.get("order", {})
        catalog_id = order_data.get("catalog_id", "")
        order_text = order_data.get("text", "")
        product_items = order_data.get("product_items", [])
        
        # Log order details
        logger.info(f"Order details - Catalog: {catalog_id}, Text: {order_text}")
        logger.info(f"Order products: {json.dumps(product_items)}")
        
        # Update user session history
        update_session_history(user_id, "user", f"Placed an order with {len(product_items)} item(s)")
        
        # Initialize cart with ordered items
        from models.cart import clear_cart
        clear_cart(user_id)
        
        # Add items to cart
        total_items = 0 
        total_price = 0
        for item in product_items:
            product_id = item.get("product_retailer_id", "")
            quantity = item.get("quantity", 1)
            
            # Add to cart
            from models.cart import add_to_cart_with_details
            
            # Get item price and currency
            item_price = item.get("item_price", 0)
            currency = item.get("currency", "GHS")
            
            # Add to cart with provided details
            success = add_to_cart_with_details(
                user_id, 
                product_id, 
                quantity, 
                price=item_price,
                currency=currency
            )
            
            if success:
                total_items += quantity
                total_price += item_price * quantity
        # Create order from cart
        from handlers.checkout import handle_confirm_checkout
        handle_confirm_checkout(user_id)
        
        return True
    except Exception as e:
        logger.error(f"Error processing order message: {str(e)}")
        
        # Send error message to user
        from services.messenger import send_text_message
        send_text_message(
            user_id, 
            "Sorry, there was a problem processing your order. Please try again or contact our support team."
        )
        return False


def handle_location_message(user_id, message):
    """Handle location messages from WhatsApp"""
    try:
        logger.info(f"Received location message from {user_id}")
        
        # Extract location data
        location = message.get("location", {})
        latitude = location.get("latitude", 0)
        longitude = location.get("longitude", 0)
        
        logger.info(f"Location coordinates: {latitude}, {longitude}")
        
        # Update user session history
        update_session_history(user_id, "user", f"Shared location: {latitude}, {longitude}")
        
        # Check if we're waiting for a location for shipping
        current_action = get_current_action(user_id)
        
        if current_action == "awaiting_shipping_location":
            # User shared location for shipping during checkout
            from handlers.checkout import handle_shipping_location
            handle_shipping_location(user_id, latitude, longitude)
        else:
            # User shared location but we weren't expecting it
            # We can offer to use it for browsing nearby stores or finding products
            send_text_message(
                user_id,
                "Thank you for sharing your location. Would you like to use this as your delivery address for future orders?"
            )
            
            # Offer options
            buttons = [
                {"type": "reply", "reply": {"id": "save_location_address", "title": "Save as Address"}},
                {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
            ]
            from services.messenger import send_button_message
            send_button_message(
                user_id,
                "Location Shared",
                "What would you like to do next?",
                buttons
            )
        
        return True
    except Exception as e:
        logger.error(f"Error processing location message: {str(e)}")
        
        # Send error message to user
        from services.messenger import send_text_message
        send_text_message(
            user_id, 
            "Sorry, there was a problem processing your location. Please try again or contact our support team."
        )
        return False

def handle_save_location_address(user_id):
    """Save a shared location as an address for future use"""
    send_text_message(
        user_id,
        "To save this location, please provide a name for this address (e.g., 'Home', 'Work', etc.) and your contact number."
    )
    
    # Set current action
    set_current_action(user_id, "awaiting_location_address_name")
    
    return True

def handle_location_address_name(user_id, name_text):
    """Handle the name provided for a location address"""
    # In a real implementation, this would save the location to the user's saved addresses
    # For this demo, just acknowledge
    send_text_message(
        user_id,
        f"Thank you! I've saved this location as '{name_text}' for future deliveries."
    )
    
    # Reset action
    set_current_action(user_id, None)
    
    # Offer to browse products
    buttons = [
        {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
    ]
    
    send_button_message(
        user_id,
        "Address Saved",
        "Would you like to browse our products?",
        buttons
    )
    
    return True

def handle_image_message(user_id, message):
    """Handle image messages from the user"""
    # In a real app, we might do image recognition to identify products
    # For now, just acknowledge receipt
    from services.messenger import send_text_message
    send_text_message(
        user_id,
        "I received your image. If you're looking for a similar product, please describe what you're looking for in text."
    )
    
    # Update user session history
    update_session_history(user_id, "user", "Sent an image")

@app.route("/", methods=["GET"])
def home():
    """Home route for checking if service is running"""
    return "WhatsApp E-commerce Bot is running!"

def setup_app():
    """Initialize app components"""
    logger.info("Setting up application...")
    
    # Initialize product catalog
    initialize_catalog()
    
    logger.info("Application setup complete")

def start_app(use_ngrok=True):
    """Start the Flask application"""
    setup_app()
    
    webhook_url = None
    if use_ngrok:
        webhook_url = start_ngrok_tunnel(PORT)
    
    try:
        logger.info(f"Starting Flask app on port {PORT}")
        app.run(debug=DEBUG, port=PORT)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        if use_ngrok:
            stop_ngrok()
    except Exception as e:
        logger.error(f"Error running app: {str(e)}")
        if use_ngrok:
            stop_ngrok()

if __name__ == "__main__":
    start_app(False)