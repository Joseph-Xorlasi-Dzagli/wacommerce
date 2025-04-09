import datetime
from models.cart import get_cart, get_cart_total, format_cart_summary, clear_cart
from models.order import create_order, get_order_by_id, update_order_status, update_payment_status, set_shipping_address, set_shipping_method
from models.session import set_current_action, get_current_action, get_last_context, set_last_context, update_session_history
from services.messenger import send_text_message, send_button_message, send_list_message, send_template_message
from utils.logger import get_logger
from geopy.geocoders import Nominatim
from services.messenger import send_text_message

logger = get_logger(__name__)

def handle_checkout(user_id):
    """Handle checkout intent, starting the checkout flow"""
    logger.info(f"Handling checkout for user {user_id}")
    
    # Check if cart has items
    cart = get_cart(user_id)
    
    if not cart or len(cart) == 0:
        send_text_message(user_id, "Your cart is empty. Please add some products before checking out.")
        
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
        ]
        
        send_button_message(user_id, "Empty Cart", "Start shopping?", buttons)
        return True
    
    # Show cart summary with confirmation button
    cart_summary = format_cart_summary(user_id)
    
    # Add terms of service notice
    tos_message = (
        f"{cart_summary}\n\n"
        f"*Terms of Service:*\n"
        f"By proceeding with checkout, you agree to our terms of service and privacy policy. "
        f"Your order will be processed and delivered according to our shipping policies."
    )
    
    buttons = [
        {"type": "reply", "reply": {"id": "confirm_checkout", "title": "Confirm Checkout"}},
        {"type": "reply", "reply": {"id": "view_cart", "title": "Edit Cart"}}
    ]
    
    send_button_message(
        user_id,
        "Confirm Order",
        tos_message,
        buttons
    )
    
    # Set current action
    set_current_action(user_id, "awaiting_checkout_confirmation")
    
    return True

def handle_payment_selection(user_id, payment_method):
    """Handle payment method selection"""
    logger.info(f"Handling payment selection for user {user_id}, method={payment_method}")
    
    # Get order ID from context
    context = get_last_context(user_id)
    
    if not context or "order_id" not in context:
        send_text_message(user_id, "Sorry, there was a problem with your order. Please try again.")
        return False
    
    order_id = context["order_id"]
    
    # Handle different payment methods
    if payment_method == "payment_cod":
        # Cash on Delivery
        return handle_cod_payment(user_id, order_id)
    elif payment_method == "payment_new_momo":
        # New mobile money account
        return handle_new_momo_request(user_id, order_id)
    elif payment_method.startswith("payment_momo_"):
        # Existing mobile money account
        account_id = payment_method.replace("payment_momo_", "")
        return handle_existing_momo_payment(user_id, order_id, account_id)
    else:
        send_text_message(user_id, "Sorry, that payment method is not supported. Please choose another option.")
        # Re-display payment options
        return handle_confirm_checkout(user_id)

def handle_new_momo_request(user_id, order_id):
    """Request details for a new mobile money account"""
    from config import MOBILE_MONEY_NETWORKS
    
    # Display network selection options
    network_rows = []
    for network in MOBILE_MONEY_NETWORKS:
        network_rows.append({
            "id": f"momo_network_{network}",
            "title": network,
            "description": f"Pay with {network} Mobile Money"
        })
    
    sections = [{
        "title": "Select Payment Provider",
        "rows": network_rows
    }]
    
    send_list_message(
        user_id,
        "Mobile Money Payment",
        f"Order #{order_id} - Please select your Payment Provider:",
        "Select Network",
        sections
    )
    
    # Store order_id and payment_method in context
    set_last_context(user_id, {
        "action": "checkout",
        "order_id": order_id,
        "step": "awaiting_momo_network"
    })
    
    # Set current action
    set_current_action(user_id, "awaiting_momo_network")
    
    return True

def handle_momo_network_selection(user_id, network):
    """Handle mobile money network selection"""
    # Get order ID from context
    context = get_last_context(user_id)
    
    if not context or "order_id" not in context:
        send_text_message(user_id, "Sorry, there was a problem with your order. Please try again.")
        return False
    
    order_id = context["order_id"]
    
    # Request mobile money number
    send_text_message(
        user_id,
        f"Please enter your {network} mobile money number in the format: 024XXXXXXX"
    )
    
    # Update context with selected network
    set_last_context(user_id, {
        "action": "checkout",
        "order_id": order_id,
        "step": "awaiting_momo_number",
        "network": network
    })
    
    # Set current action
    set_current_action(user_id, "awaiting_momo_number")
    
    return True

def handle_momo_number_submission(user_id, number_text):
    """Handle mobile money number submission"""
    # Validate phone number format (simple validation)
    import re
    if not re.match(r'^0[0-9]{9}$', number_text):
        send_text_message(
            user_id,
            "The mobile money number format is invalid. Please provide a valid 10-digit number starting with 0 (e.g., 0241234567)."
        )
        return False
    
    # Get context data
    context = get_last_context(user_id)
    
    if not context or "order_id" not in context or "network" not in context:
        send_text_message(user_id, "Sorry, there was a problem with your order. Please try again.")
        return False
    
    order_id = context["order_id"]
    network = context["network"]
    
    # Store the new mobile money account
    from models.session import get_user_name
    user_name = get_user_name(user_id)
    
    # In a real app, this would be saved to a database
    new_account = {
        "id": f"momo_{int(datetime.time.time())}",
        "network": network,
        "number": number_text,
        "name": user_name,
        "is_default": False,
        "last_used": datetime.now().isoformat()
    }
    
    # Send confirmation message
    send_text_message(
        user_id,
        f"Thank you. We'll process payment through your {network} mobile money account {number_text}.\n\n"
        f"You will receive a prompt on your phone to authorize the payment. Please complete the authorization to proceed with your order."
    )
    
    # Update payment status
    update_payment_status(order_id, "pending_momo")
    
    # Store payment details in order
    order = get_order_by_id(order_id)
    if order:
        order["payment_details"] = {
            "method": "mobile_money",
            "network": network,
            "number": number_text
        }
    
    # Proceed to shipping options
    return handle_shipping_options(user_id, order_id)

def handle_existing_momo_payment(user_id, order_id, account_id):
    """Handle payment with existing mobile money account"""
    from config import MOCK_PAYMENT_ACCOUNTS
    
    # Find the selected account
    selected_account = None
    for account in MOCK_PAYMENT_ACCOUNTS:
        if account["id"] == account_id:
            selected_account = account
            break
    
    if not selected_account:
        send_text_message(user_id, "Sorry, we couldn't find that payment account. Please try again.")
        return False
    
    # Send confirmation message
    send_text_message(
        user_id,
        f"Thank you. We'll process payment through your {selected_account['network']} mobile money account {selected_account['number']}.\n\n"
        f"You will receive a prompt on your phone to authorize the payment. Please complete the authorization to proceed with your order."
    )
    
    # Update payment status
    update_payment_status(order_id, "pending_momo")
    
    # Store payment details in order
    order = get_order_by_id(order_id)
    if order:
        order["payment_details"] = {
            "method": "mobile_money",
            "network": selected_account["network"],
            "number": selected_account["number"]
        }
    
    # Proceed to shipping options
    return handle_shipping_options(user_id, order_id)

def handle_confirm_checkout(user_id):
    """Handle checkout confirmation, proceeding to payment"""
    logger.info(f"Handling checkout confirmation for user {user_id}")
    
    # Create order from cart
    order = create_order(user_id)
    
    if not order:
        send_text_message(user_id, "Sorry, there was a problem creating your order. Please try again.")
        return False
    
    # Store order ID in context
    set_last_context(user_id, {
        "action": "checkout",
        "order_id": order["order_id"]
    })
    
    # Present payment options
    from config import MOCK_PAYMENT_ACCOUNTS
    
    # Create sections for the list message
    sections = []
    
    # Add saved mobile money accounts section if available
    if MOCK_PAYMENT_ACCOUNTS:
        saved_accounts_rows = []
        for account in MOCK_PAYMENT_ACCOUNTS:
            saved_accounts_rows.append({
                "id": f"payment_momo_{account['id']}",
                "title": f"{account['network']} - {account['number']}",
                "description": f"{'(Default)' if account['is_default'] else ''}"
            })
        
        sections.append({
            "title": "Saved Payment Accounts",
            "rows": saved_accounts_rows
        })
    
    # Add other options section
    other_options_rows = [
        {
            "id": "payment_new_momo", 
            "title": "Add Payment Account", 
            "description": "Pay with a different mobile money account"
        },
        {
            "id": "payment_cod", 
            "title": "Cash on Delivery", 
            "description": "Pay when you receive your order"
        }
    ]
    
    sections.append({
        "title": "Other Payment Options",
        "rows": other_options_rows
    })
    
    send_list_message(
        user_id,
        "Choose Payment Method",
        f"Order #{order['order_id']} - Total: ${order['total']:.2f}",
        "Select Payment",
        sections
    )
    
    # Set current action
    set_current_action(user_id, "awaiting_payment_method")
    
    return True

def handle_payment_selection(user_id, payment_method):
    """Handle payment method selection"""
    logger.info(f"Handling payment selection for user {user_id}, method={payment_method}")
    
    # Get order ID from context
    context = get_last_context(user_id)
    
    if not context or "order_id" not in context:
        send_text_message(user_id, "Sorry, there was a problem with your order. Please try again.")
        return False
    
    order_id = context["order_id"]
    
    # Handle different payment methods
    if payment_method == "payment_card":
        return handle_card_payment(user_id, order_id)
    elif payment_method == "payment_paypal":
        return handle_paypal_payment(user_id, order_id)
    elif payment_method == "payment_bank":
        return handle_bank_payment(user_id, order_id)
    elif payment_method == "payment_cod":
        return handle_cod_payment(user_id, order_id)
    else:
        send_text_message(user_id, "Sorry, that payment method is not supported. Please choose another option.")
        # Re-display payment options
        return handle_confirm_checkout(user_id)

def handle_card_payment(user_id, order_id):
    """Handle credit/debit card payment"""
    # In a real implementation, this would generate a payment link to a secure payment gateway
    
    # Set action while waiting for payment
    set_current_action(user_id, "awaiting_payment_completion")
    
    # Generate mock payment link
    payment_link = f"https://example.com/pay/{order_id}"
    
    # Send payment link
    send_text_message(
        user_id, 
        f"Please complete your payment by clicking the link below. Your order will be processed once payment is confirmed.\n\n"
        f"Payment Link: {payment_link}\n\n"
        f"Order #{order_id}"
    )
    
    # In a real scenario, the payment gateway would call back to update the order status
    # For demo purposes, we'll simulate a successful payment
    update_payment_status(order_id, "paid")
    
    # Proceed to shipping options
    return handle_shipping_options(user_id, order_id)

def handle_paypal_payment(user_id, order_id):
    """Handle PayPal payment"""
    # Similar to card payment, but with PayPal
    payment_link = f"https://example.com/paypal/{order_id}"
    
    send_text_message(
        user_id, 
        f"Please complete your PayPal payment by clicking the link below.\n\n"
        f"PayPal Link: {payment_link}\n\n"
        f"Order #{order_id}"
    )
    
    # Simulate payment success
    update_payment_status(order_id, "paid")
    
    # Proceed to shipping options
    return handle_shipping_options(user_id, order_id)

def handle_bank_payment(user_id, order_id):
    """Handle bank transfer payment"""
    bank_details = (
        "*Bank Transfer Details:*\n\n"
        "Bank Name: Example Bank\n"
        "Account Name: WhatsApp Store\n"
        "Account Number: 1234567890\n"
        "Sort Code: 12-34-56\n"
        "Reference: Order " + order_id
    )
    
    send_text_message(
        user_id,
        f"{bank_details}\n\n"
        f"Please make your transfer within 48 hours to avoid order cancellation. "
        f"Your order will be processed once payment is confirmed."
    )
    
    # Set order status to awaiting payment
    update_payment_status(order_id, "pending")
    
    # Proceed to shipping options, even though payment is pending
    return handle_shipping_options(user_id, order_id)

def handle_cod_payment(user_id, order_id):
    """Handle cash on delivery payment"""
    send_text_message(
        user_id,
        f"You've selected Cash on Delivery for Order #{order_id}. "
        f"You'll pay when your order is delivered."
    )
    
    # Set payment status
    update_payment_status(order_id, "cash_on_delivery")
    
    # Proceed to shipping options
    return handle_shipping_options(user_id, order_id)

def handle_shipping_options(user_id, order_id):
    """Handle shipping options"""
    logger.info(f"Handling shipping options for user {user_id}, order_id={order_id}")
    
    # Store in context
    set_last_context(user_id, {
        "action": "checkout",
        "order_id": order_id,
        "step": "shipping"
    })
    
    # Present shipping options
    from config import MOCK_SHIPPING_ADDRESSES
    
    # Create sections for the list message
    sections = []
    
    # Add saved addresses section if available
    if MOCK_SHIPPING_ADDRESSES:
        saved_addresses_rows = []
        for address in MOCK_SHIPPING_ADDRESSES:
            # Format the address for display
            address_display = f"{address['street']}, {address['city']}"
            saved_addresses_rows.append({
                "id": f"shipping_address_{address['id']}",
                "title": f"{address['name']} - {'(Default)' if address['is_default'] else ''}",
                "description": f"{address_display}"
            })
        
        sections.append({
            "title": "Saved Addresses",
            "rows": saved_addresses_rows
        })
    
    # Add other options section
    other_options_rows = [
        {
            "id": "shipping_new_address", 
            "title": "Add Address", 
            "description": "Provide a different delivery address"
        },
        {
            "id": "shipping_location", 
            "title": "Use Current Location", 
            "description": "Share your location for delivery"
        }
    ]
    
    sections.append({
        "title": "Other Options",
        "rows": other_options_rows
    })
    
    send_list_message(
        user_id,
        "Choose Shipping Address",
        f"Order #{order_id} - How would you like to receive your order?",
        "Select Address",
        sections
    )
    
    # Set current action
    set_current_action(user_id, "awaiting_shipping_option")
    
    return True

def handle_shipping_selection(user_id, shipping_option):
    """Handle shipping address selection"""
    logger.info(f"Handling shipping selection for user {user_id}, option={shipping_option}")
    
    # Get order ID from context
    context = get_last_context(user_id)
    
    if not context or "order_id" not in context:
        send_text_message(user_id, "Sorry, there was a problem with your order. Please try again.")
        return False
    
    order_id = context["order_id"]
    
    # Handle different shipping options
    if shipping_option == "shipping_new_address":
        # Request location using the interactive location request message
        from services.messenger import send_location_request_message
        send_location_request_message(
            user_id,
            "Let us start with your delivery address. You can either manually *enter an address* or *share your current location*."
        )
        
        # Set action
        set_current_action(user_id, "awaiting_shipping_address_or_location")
        
    elif shipping_option == "shipping_location":
        # Request location
        from services.messenger import send_location_request_message
        send_location_request_message(
            user_id,
            "Please share your current location for delivery."
        )
        
        # Set action
        set_current_action(user_id, "awaiting_shipping_location")
        
    elif shipping_option.startswith("shipping_address_"):
        # Existing address selected
        address_id = shipping_option.replace("shipping_address_", "")
        return handle_existing_address_selection(user_id, order_id, address_id)
        
    else:
        send_text_message(user_id, "Sorry, that shipping option is not supported. Please choose another option.")
        # Re-display shipping options
        return handle_shipping_options(user_id, order_id)
    
    return True

def handle_message_after_location_request(user_id, message_body):
    """Handle text message received after a location request (manual address entry)"""
    # Get context
    context = get_last_context(user_id)
    
    if not context or "order_id" not in context:
        send_text_message(user_id, "Sorry, there was a problem with your order. Please try again.")
        return False
    
    order_id = context["order_id"]
    
    # Process as a shipping address
    return handle_shipping_address(user_id, message_body)

def handle_existing_address_selection(user_id, order_id, address_id):
    """Handle selection of an existing saved address"""
    from config import MOCK_SHIPPING_ADDRESSES
    
    # Find the selected address
    selected_address = None
    for address in MOCK_SHIPPING_ADDRESSES:
        if address["id"] == address_id:
            selected_address = address
            break
    
    if not selected_address:
        send_text_message(user_id, "Sorry, we couldn't find that address. Please try again.")
        return False
    
    # Format the address
    formatted_address = (
        f"{selected_address['recipient']}\n"
        f"{selected_address['street']}\n"
        f"{selected_address['city']}, {selected_address['region']}\n"
        f"Phone: {selected_address['phone']}"
    )
    
    # Set shipping address
    set_shipping_address(order_id, formatted_address)
    
    # Send confirmation
    send_text_message(
        user_id,
        f"Your order will be delivered to the following address:\n\n{formatted_address}"
    )
    
    # Complete order
    return complete_order(user_id, order_id)

def handle_shipping_address(user_id, address_text):
    """Handle shipping address submission"""
    logger.info(f"Handling shipping address for user {user_id}")
    
    # Get order ID from context
    context = get_last_context(user_id)
    
    if not context or "order_id" not in context:
        send_text_message(user_id, "Sorry, there was a problem with your order. Please try again.")
        return False
    
    order_id = context["order_id"]
    
    # Validate address format (simple validation)
    if len(address_text.split('\n')) < 3:
        send_text_message(
            user_id,
            "The address format seems incomplete. Please provide your full shipping address including recipient name, street address, city/region, and phone number."
        )
        return False
    
    # Set shipping address
    set_shipping_address(order_id, address_text)
    
    # Ask if they want to save this address for future orders
    buttons = [
        {"type": "reply", "reply": {"id": f"save_address_{order_id}", "title": "Save Address"}},
        {"type": "reply", "reply": {"id": f"no_save_address_{order_id}", "title": "Don't Save"}}
    ]
    
    send_button_message(
        user_id,
        "Save Address?",
        "Would you like to save this address for future orders?",
        buttons
    )
    
    # Set current action
    set_current_action(user_id, "awaiting_save_address_decision")
    
    return True

def handle_save_address_decision(user_id, decision, order_id):
    """Handle decision to save address"""
    if decision == "save":
        # In a real implementation, this would save to a database
        # For now, just acknowledge
        send_text_message(user_id, "Address saved for future orders.")
    
    # Complete the order
    return complete_order(user_id, order_id)

def handle_shipping_location(user_id, latitude, longitude):
    """Handle location shared for shipping"""
    logger.info(f"Handling shipping location for user {user_id}: {latitude}, {longitude}")
    
    # Get order ID from context
    context = get_last_context(user_id)
    
    if not context or "order_id" not in context:
        send_text_message(user_id, "Sorry, there was a problem with your order. Please try again.")
        return False
    
    order_id = context["order_id"]
    
    # Format the location as an address
    location_address = f"Delivery to shared location: {latitude}, {longitude}"
    
    # Set shipping address
    set_shipping_address(order_id, location_address)
    
    # Request additional delivery instructions
    send_text_message(
        user_id,
        "Thank you for sharing your location. Please provide any additional delivery instructions or landmarks to help the delivery person find you."
    )
    
    # Set current action
    set_current_action(user_id, "awaiting_delivery_instructions")
    
    return True

def handle_delivery_instructions(user_id, instructions):
    
    """Handle delivery instructions for a location-based delivery"""
    # Get order ID from context
    context = get_last_context(user_id)
    
    if not context or "order_id" not in context:
        send_text_message(user_id, "Sorry, there was a problem with your order. Please try again.")
        return False
    
    order_id = context["order_id"]
    
    # Get the current shipping address (the coordinates)
    order = get_order_by_id(order_id)
    if not order:
        send_text_message(user_id, "Sorry, there was a problem with your order. Please try again.")
        return False
    
    current_address = order.get("shipping_address", "")
    
    # Append the instructions
    updated_address = f"{current_address}\n\nDelivery instructions: {instructions}"
    
    # Update the shipping address
    set_shipping_address(order_id, updated_address)
    
    # Complete the order
    return complete_order(user_id, order_id)

def handle_momo_number_submission(user_id, number_text):
    """Handle mobile money number submission"""
    # Validate phone number format (simple validation for Ghana numbers)
    import re
    if not re.match(r'^0[2345]\d{8}$', number_text):
        send_text_message(
            user_id,
            "The mobile money number format is invalid. Please provide a valid 10-digit Ghana number starting with 02, 03, 04, or 05 (e.g., 0241234567)."
        )
        return False
    
    # Get context data
    context = get_last_context(user_id)
    
    if not context or "order_id" not in context or "network" not in context:
        send_text_message(user_id, "Sorry, there was a problem with your order. Please try again.")
        return False
    
    order_id = context["order_id"]
    network = context["network"]
    
    # Store the new mobile money account
    from models.session import get_user_name
    import time
    from datetime import datetime
    
    user_name = get_user_name(user_id)
    
    # In a real app, this would be saved to a database
    new_account = {
        "id": f"momo_{int(time.time())}",
        "network": network,
        "number": number_text,
        "name": user_name,
        "is_default": False,
        "last_used": datetime.now().isoformat()
    }
    
    # Send confirmation message
    send_text_message(
        user_id,
        f"Thank you. We'll process payment through your {network} mobile money account {number_text}.\n\n"
        f"You will receive a prompt on your phone to authorize the payment. Please complete the authorization to proceed with your order."
    )
    
    # Update payment status
    from models.order import update_payment_status, get_order_by_id
    update_payment_status(order_id, "pending_momo")
    
    # Store payment details in order
    order = get_order_by_id(order_id)
    if order:
        order["payment_details"] = {
            "method": "mobile_money",
            "network": network,
            "number": number_text
        }
    
    # Proceed to shipping options
    from handlers.checkout import handle_shipping_options
    return handle_shipping_options(user_id, order_id)

def handle_location_message(user_id, message):
    """Handle location messages from WhatsApp"""
    try:
        logger.info(f"Received location message from {user_id}")
        
        # Extract complete location data
        location = message.get("location", {})
        latitude = location.get("latitude", 0)
        longitude = location.get("longitude", 0)
        address = location.get("address", "")
        name = location.get("name", "")
        
        logger.info(f"Location data received: {name}, {address}, Coordinates: {latitude}, {longitude}")
        
        # Format a complete location text
        location_text = ""
        if name:
            location_text += f"{name}\n"
        if address:
            location_text += f"{address}\n"
        location_text += f"Coordinates: {latitude}, {longitude}"
        
        geolocator = Nominatim(user_agent="apsel")
    
        location = geolocator.reverse(f"{latitude}, {longitude}")

        logger.info(f"Location: {location}")

        # Update user session history
        update_session_history(user_id, "user", f"Shared location: {location_text}")
        
        # Check if we're waiting for a location for shipping
        current_action = get_current_action(user_id)
        
        if current_action == "awaiting_shipping_location" or current_action == "awaiting_shipping_address_or_location":
            # User shared location for shipping during checkout
            # Get order ID from context
            context = get_last_context(user_id)
            
            if not context or "order_id" not in context:
                send_text_message(user_id, "Sorry, there was a problem with your order. Please try again.")
                return False
            
            order_id = context["order_id"]
            
            # Set the formatted location as shipping address
            from models.order import set_shipping_address
            set_shipping_address(order_id, location)
            
            # Send confirmation message
            send_text_message(
                user_id,
                f"Thank you for sharing your location. Your order will be delivered to:\n\n{location}"
            )
            
            # Complete the order
            from handlers.checkout import complete_order
            return complete_order(user_id, order_id)
        else:
            # User shared location but we weren't expecting it
            # We can offer to save it for future use
            send_text_message(
                user_id,
                f"Thank you for sharing your location:\n\n{location}\n\nWould you like to save this as your delivery address for future orders?"
            )
            
            # Offer options
            buttons = [
                {"type": "reply", "reply": {"id": "save_location_address", "title": "Save as Address"}},
                {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
            ]
            
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
        
        send_text_message(
            user_id, 
            "Sorry, there was a problem processing your location. Please try again or contact our support team."
        )
        return False

def complete_order(user_id, order_id):

    """Complete the order process"""
    logger.info(f"Completing order for user {user_id}, order_id={order_id}")
    
    # Update order status
    update_order_status(order_id, "confirmed")
    
    # Send order confirmation
    from models.order import format_order_summary
    order_summary = format_order_summary(order_id)
    
    send_text_message(
        user_id,
        f"🎉 *Your order has been confirmed!*\n\n"
        f"{order_summary}\n\n"
        f"Thank you for shopping with us. You'll receive updates as your order progresses."
    )
    
    # Order management options
    buttons = [
        {"type": "reply", "reply": {"id": f"track_{order_id}", "title": "Track Order"}},
        {"type": "reply", "reply": {"id": "browse", "title": "Continue Shopping"}}
    ]
    
    send_button_message(
        user_id,
        "Order Confirmed",
        f"What would you like to do next?",
        buttons
    )
    
    # Reset current action
    # set_current_action(user_id, None)
    
    return True