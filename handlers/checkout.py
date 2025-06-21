from datetime import datetime, timedelta
from models.cart import get_cart, format_cart_summary, clear_cart
from models.order import create_order, get_order_by_id, update_order_status, update_payment_status, set_shipping_address, set_shipping_method
from models.session import get_current_action, set_current_action, get_last_context, set_last_context, update_session_history
from models.customer import get_customer_payment_accounts, get_customer_addresses, save_customer_address, save_customer_payment_account, get_or_create_customer
from services.messenger import send_payment_link_message, send_text_message, send_button_message, send_list_message, send_location_message, send_location_request_message
from services.inventory import check_inventory_availability, format_inventory_message, update_cart_with_available_stock
from utils.logger import get_logger
from geopy.geocoders import Nominatim

logger = get_logger(__name__)

def handle_checkout(business_context, user_id):
    """Handle checkout intent, starting the checkout flow with business context"""
    logger.info(f"Handling checkout for user {user_id}, business={business_context.get('business_id')}")
    business_id = business_context.get('business_id')
    
    # Ensure customer exists in database
    try:
        from models.session import get_user_name
        user_name = get_user_name(user_id)
        customer = get_or_create_customer(user_id, user_name, business_id)
        if customer:
            logger.info(f"Customer ready for checkout: {customer.get('id', 'unknown')}")
    except Exception as e:
        logger.warning(f"Could not create/get customer for {user_id}: {str(e)}")
    
    # Check if cart has items
    cart = get_cart(business_context, user_id)
    
    if not cart or len(cart) == 0:
        send_text_message(business_context, user_id, "Your cart is empty. Please add some products before checking out.")
        
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
        ]
        
        send_button_message(business_context, user_id, "Empty Cart", "Start shopping?", buttons)
        return True
    
    # Show cart summary with confirmation button
    cart_summary = format_cart_summary(business_context, user_id)
    
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
        business_context,
        user_id,
        "Confirm Order",
        tos_message,
        buttons
    )
    
    # Set current action
    set_current_action(user_id, "awaiting_checkout_confirmation")
    
    return True

def handle_confirm_checkout(business_context, user_id):
    """Handle checkout confirmation with inventory verification and business context"""
    logger.info(f"Handling checkout confirmation for user {user_id}, business={business_context.get('business_id')}")
    
    # Check if cart has items
    cart = get_cart(business_context, user_id)
    
    if not cart or len(cart) == 0:
        send_text_message(business_context, user_id, "Your cart is empty. Please add some products before checking out.")
        
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
        ]
        
        send_button_message(business_context, user_id, "Empty Cart", "Start shopping?", buttons)
        return True
    
    # Check inventory availability before proceeding
    try:
        inventory_results = check_inventory_availability(business_context, cart)
        
        if inventory_results["has_issues"]:
            # Store inventory results in context for later use
            set_last_context(user_id, {
                "action": "checkout_inventory_check",
                "inventory_results": inventory_results,
                "business_id": business_context.get('business_id')
            })
            
            # Format and send inventory message
            inventory_message = format_inventory_message(inventory_results)
            
            if inventory_results["modified_cart"]:
                # Some items available - offer to proceed or cancel
                buttons = [
                    {"type": "reply", "reply": {"id": "proceed_with_available", "title": "Proceed to Checkout"}},
                    {"type": "reply", "reply": {"id": "cancel_inventory_order", "title": "Cancel Order"}}
                ]
                
                send_button_message(
                    business_context,
                    user_id,
                    "Inventory Check",
                    inventory_message,
                    buttons
                )
            else:
                # No items available - only option is to cancel
                send_text_message(business_context, user_id, inventory_message)
                
                buttons = [
                    {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}},
                    {"type": "reply", "reply": {"id": "view_cart", "title": "View Cart"}}
                ]
                
                send_button_message(
                    business_context,
                    user_id,
                    "Order Cannot Proceed",
                    "All items in your cart are currently out of stock. What would you like to do?",
                    buttons
                )
            
            # Set current action to wait for inventory decision
            set_current_action(user_id, "awaiting_inventory_decision")
            return True
    except Exception as e:
        logger.warning(f"Error checking inventory for {user_id}: {str(e)}")
        # Continue with checkout if inventory check fails
    
    # All items available - proceed with normal checkout flow
    return proceed_to_payment_selection(business_context, user_id)

def proceed_to_payment_selection(business_context, user_id):
    """Proceed to payment selection after inventory check passes"""
    # Create order from cart
    order = create_order(business_context, user_id)
    
    if not order:
        send_text_message(business_context, user_id, "Sorry, there was a problem creating your order. Please try again.")
        return False
    
    # Store order ID in context
    set_last_context(user_id, {
        "action": "checkout",
        "order_id": order["order_id"],
        "business_id": business_context.get('business_id')
    })
    
    # Get customer's saved payment accounts
    try:
        payment_accounts = get_customer_payment_accounts(business_context, user_id)
        logger.info(f"Found {len(payment_accounts)} payment accounts for user {user_id}")
    except Exception as e:
        logger.error(f"Error fetching payment accounts: {str(e)}")
        payment_accounts = []
    
    # Present payment options
    sections = []
    
    # Add saved payment accounts section if available
    if payment_accounts:
        saved_accounts_rows = []
        for account in payment_accounts:
            saved_accounts_rows.append({
                "id": f"payment_momo_{account['id']}",
                "title": f"{account.get('account_provider', 'Mobile Money')} - {account.get('account_number', '')}",
                "description": f"{'(Default)' if account.get('is_default', False) else ''}"
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
        }
    ]
    
    # If no saved accounts, show customer's current number as option
    if not payment_accounts:
        try:
            formatted_number = f"0{user_id[3:]}" 
            # Identify network provider based on first 3 digits
            network_prefix = formatted_number[:3]
            if network_prefix in ["024", "025", "054", "055"]:
                network_name = "MTN"
            elif network_prefix in ["020", "050"]:
                network_name = "Vodafone"
            elif network_prefix in ["026", "056", "027", "057"]:
                network_name = "AirtelTigo"
            else:
                network_name = "Mobile Money"
            
            other_options_rows.insert(0, {
                "id": f"payment_current_number_{formatted_number}",
                "title": f"{network_name} - {formatted_number}",
                "description": "Pay with your current WhatsApp number"
            })
        except Exception as e:
            logger.warning(f"Could not format user number {user_id}: {str(e)}")
    
    other_options_rows.append({
        "id": "payment_cod", 
        "title": "Cash on Delivery", 
        "description": "Pay when you receive your order"
    })
    
    sections.append({
        "title": "Other Payment Options",
        "rows": other_options_rows
    })
    
    send_list_message(
        business_context,
        user_id,
        "Choose Payment Method",
        f"Order #{order['order_id']} - Total: GHS{order['total']:.2f}",
        "Select Payment",
        sections
    )
    
    # Set current action
    set_current_action(user_id, "awaiting_payment_method")
    
    return True

def handle_proceed_with_available(business_context, user_id):
    """Handle customer decision to proceed with available items"""
    logger.info(f"Handling proceed with available items for user {user_id}, business={business_context.get('business_id')}")
    
    # Get inventory results from context
    context = get_last_context(user_id)
    
    if not context or "inventory_results" not in context:
        send_text_message(business_context, user_id, "Sorry, there was a problem processing your request. Please try checkout again.")
        return False
    
    inventory_results = context["inventory_results"]
    
    # Update cart with available items only
    if inventory_results["modified_cart"]:
        try:
            update_cart_with_available_stock(business_context, user_id, inventory_results["modified_cart"])
            
            # Show updated cart summary
            cart_summary = format_cart_summary(business_context, user_id)
            
            send_text_message(
                business_context,
                user_id,
                f"✅ *Cart Updated*\n\n{cart_summary}\n\nProceeding to payment..."
            )
            
            # Proceed to payment selection
            return proceed_to_payment_selection(business_context, user_id)
        except Exception as e:
            logger.error(f"Error updating cart with available stock: {str(e)}")
            send_text_message(business_context, user_id, "Sorry, there was an error updating your cart. Please try again.")
            return False
    else:
        # Shouldn't happen, but handle gracefully
        send_text_message(business_context, user_id, "No items are available to proceed with. Please browse our products.")
        
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
        ]
        
        send_button_message(business_context, user_id, "No Items", "Start shopping?", buttons)
        return True

def handle_cancel_inventory_order(business_context, user_id):
    """Handle customer decision to cancel order due to inventory issues"""
    logger.info(f"Handling cancel inventory order for user {user_id}, business={business_context.get('business_id')}")
    
    # Clear the current action
    set_current_action(user_id, None)
    
    # Send confirmation message
    send_text_message(
        business_context,
        user_id,
        "Your order has been cancelled. Your cart items remain saved if you'd like to try again later."
    )
    
    # Offer options to continue
    buttons = [
        {"type": "reply", "reply": {"id": "view_cart", "title": "View Cart"}},
        {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
    ]
    
    send_button_message(
        business_context,
        user_id,
        "Order Cancelled",
        "What would you like to do next?",
        buttons
    )
    
    return True

def handle_payment_selection(business_context, user_id, payment_method):
    """Handle payment method selection with business context"""
    logger.info(f"Handling payment selection for user {user_id}, method={payment_method}, business={business_context.get('business_id')}")
    
    # Get order ID from context
    context = get_last_context(user_id)
    
    if not context or "order_id" not in context:
        send_text_message(business_context, user_id, "Sorry, there was a problem with your order. Please try again.")
        return False
    
    order_id = context["order_id"]
    
    # Handle different payment methods
    if payment_method == "payment_cod":
        return handle_cod_payment(business_context, user_id, order_id)
    elif payment_method == "payment_new_momo":
        return handle_new_momo_request(business_context, user_id, order_id)
    elif payment_method.startswith("payment_current_number_"):
        current_number = payment_method.replace("payment_current_number_", "")
        return handle_current_number_payment(business_context, user_id, order_id, current_number)
    elif payment_method.startswith("payment_momo_"):
        account_id = payment_method.replace("payment_momo_", "")
        return handle_existing_momo_payment(business_context, user_id, order_id, account_id)
    else:
        send_text_message(business_context, user_id, "Sorry, that payment method is not supported. Please choose another option.")
        return handle_confirm_checkout(business_context, user_id)

def handle_new_momo_request(business_context, user_id, order_id):
    """Request details for a new mobile money account"""
    # Get available networks from business settings or use default
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    # Default networks
    mobile_money_networks = ["MTN", "Vodafone", "AirtelTigo"]
    
    # Try to get business-specific networks
    if db and business_id:
        try:
            settings_ref = db.collection('business_settings').document(business_id)
            settings_doc = settings_ref.get()
            
            if settings_doc.exists:
                settings_data = settings_doc.to_dict()
                checkout_settings = settings_data.get('checkout', {})
                custom_networks = checkout_settings.get('payment_methods', {}).get('mobile_money_networks')
                if custom_networks:
                    mobile_money_networks = custom_networks
        except Exception as e:
            logger.warning(f"Could not fetch business payment networks: {str(e)}")
    
    # Display network selection options
    network_rows = []
    for network in mobile_money_networks:
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
        business_context,
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
        "step": "awaiting_momo_network",
        "business_id": business_context.get('business_id')
    })
    
    # Set current action
    set_current_action(user_id, "awaiting_momo_network")
    
    return True

def handle_momo_network_selection(business_context, user_id, network):
    """Handle mobile money network selection"""
    # Get order ID from context
    context = get_last_context(user_id)
    
    if not context or "order_id" not in context:
        send_text_message(business_context, user_id, "Sorry, there was a problem with your order. Please try again.")
        return False
    
    order_id = context["order_id"]
    
    # Request mobile money number
    send_text_message(
        business_context,
        user_id,
        f"Please provide your {network} mobile money number (format: 0XXXXXXXXX)"
    )
    
    # Update context with selected network
    set_last_context(user_id, {
        "action": "checkout",
        "order_id": order_id,
        "step": "awaiting_momo_number",
        "network": network,
        "business_id": business_context.get('business_id')
    })
    
    # Set current action
    set_current_action(user_id, "awaiting_momo_number")
    
    return True

def handle_momo_number_submission(business_context, user_id, number_text):
    """Handle mobile money number submission"""
    import re
    import time
    
    try:
        # Validate phone number format (Ghana numbers)
        if not re.match(r'^0[2345]\d{8}$', number_text.strip()):
            send_text_message(
                business_context,
                user_id,
                "❌ Invalid mobile money number format. Please provide a valid 10-digit Ghana number starting with 02, 03, 04, or 05 (e.g., 0241234567)."
            )
            return False
        
        # Get context data
        context = get_last_context(user_id)
        
        if not context or "order_id" not in context or "network" not in context:
            send_text_message(business_context, user_id, "❌ Session expired. Please start checkout again.")
            return False
        
        order_id = context["order_id"]
        network = context["network"]
        business_id = business_context.get('business_id')
        
        # Get user name for account
        from models.session import get_user_name
        user_name = get_user_name(user_id)
        
        # Generate payment URL (replace with real payment gateway)
        payment_url = f"https://payment.example.com/pay/{order_id}?network={network}&phone={number_text}"
        
        # Update payment status in order
        update_payment_status(order_id, "pending_momo")
        
        # Store payment details in order
        order = get_order_by_id(order_id)
        if order:
            order["payment_details"] = {
                "method": "mobile_money",
                "network": network,
                "number": number_text.strip(),
                "payment_url": payment_url
            }
        
        # Send payment confirmation with link
        send_payment_link_message(
            business_context,
            user_id,
            order_id,
            network,
            number_text.strip(),
            payment_url
        )
        
        # Save the payment account for future use
        try:
            save_customer_payment_account(user_id, network, number_text.strip(), user_name, business_id)
        except Exception as e:
            logger.warning(f"Could not save payment account: {str(e)}")
        
        # Clear current action
        set_current_action(user_id, None)
        
        # Proceed to shipping options
        return handle_shipping_options(business_context, user_id, order_id)
        
    except Exception as e:
        logger.error(f"Error handling mobile money number submission: {str(e)}")
        send_text_message(business_context, user_id, "❌ Sorry, there was an error processing your payment details. Please try again.")
        return False

def handle_current_number_payment(business_context, user_id, order_id, current_number):
    """Handle payment with customer's current WhatsApp number"""
    # Get available networks
    mobile_money_networks = ["MTN", "Vodafone", "AirtelTigo"]
    
    # Display network selection options for the current number
    network_rows = []
    for network in mobile_money_networks:
        network_rows.append({
            "id": f"current_momo_network_{network}",
            "title": network,
            "description": f"Pay with {network} Mobile Money using {current_number}"
        })
    
    sections = [{
        "title": f"Select Payment Provider for {current_number}",
        "rows": network_rows
    }]
    
    send_list_message(
        business_context,
        user_id,
        "Mobile Money Payment",
        f"Order #{order_id} - Please select your Payment Provider:",
        "Select Network",
        sections
    )
    
    # Store order_id and current number in context
    set_last_context(user_id, {
        "action": "checkout",
        "order_id": order_id,
        "step": "awaiting_current_momo_network",
        "current_number": current_number,
        "business_id": business_context.get('business_id')
    })
    
    # Set current action
    set_current_action(user_id, "awaiting_current_momo_network")
    
    return True

def handle_current_momo_network_selection(business_context, user_id, network):
    """Handle mobile money network selection for current number"""
    # Get context data
    context = get_last_context(user_id)
    
    if not context or "order_id" not in context or "current_number" not in context:
        send_text_message(business_context, user_id, "Sorry, there was a problem with your order. Please try again.")
        return False
    
    order_id = context["order_id"]
    current_number = context["current_number"]
    business_id = business_context.get('business_id')
    
    # Generate a payment URL
    payment_url = f"https://payment.example.com/pay/{order_id}?network={network}&phone={current_number}"
    
    # Update payment status
    update_payment_status(order_id, "pending_momo")
    
    # Store payment details in order
    order = get_order_by_id(order_id)
    if order:
        order["payment_details"] = {
            "method": "mobile_money",
            "network": network,
            "number": current_number,
            "payment_url": payment_url
        }
    
    # Send payment link message
    send_payment_link_message(
        business_context,
        user_id,
        order_id,
        network,
        current_number,
        payment_url
    )
    
    # Save the payment account for future use
    try:
        from models.session import get_user_name
        user_name = get_user_name(user_id)
        save_customer_payment_account(user_id, network, current_number, user_name, business_id)
    except Exception as e:
        logger.warning(f"Could not save payment account: {str(e)}")
    
    # Proceed to shipping options
    return handle_shipping_options(business_context, user_id, order_id)

def handle_existing_momo_payment(business_context, user_id, order_id, account_id):
    """Handle payment with existing mobile money account"""
    try:
        # Get saved payment accounts from database
        saved_payment_accounts = get_customer_payment_accounts(business_context, user_id)
        
        # Find the selected account
        selected_account = None
        for account in saved_payment_accounts:
            if str(account.get("id", "")) == str(account_id):
                selected_account = account
                break
        
        if not selected_account:
            send_text_message(business_context, user_id, "Sorry, we couldn't find that payment account. Please try again.")
            return False
        
        # Generate a payment URL
        payment_url = f"https://payment.example.com/pay/{order_id}?network={selected_account.get('account_provider', '')}&phone={selected_account.get('account_number', '')}"
        
        # Update payment status
        update_payment_status(order_id, "pending_momo")
        
        # Store payment details in order
        order = get_order_by_id(order_id)
        if order:
            order["payment_details"] = {
                "method": "mobile_money",
                "network": selected_account.get("account_provider", ""),
                "number": selected_account.get("account_number", ""),
                "payment_url": payment_url
            }
        
        # Send payment link message
        send_payment_link_message(
            business_context,
            user_id,
            order_id,
            selected_account.get("account_provider", ""),
            selected_account.get("account_number", ""),
            payment_url
        )
        
        # Proceed to shipping options
        return handle_shipping_options(business_context, user_id, order_id)
        
    except Exception as e:
        logger.error(f"Error handling existing momo payment: {str(e)}")
        send_text_message(business_context, user_id, "Sorry, there was an error processing your payment. Please try again.")
        return False

def handle_cod_payment(business_context, user_id, order_id):
    """Handle cash on delivery payment"""
    send_text_message(
        business_context,
        user_id,
        f"You've selected Cash on Delivery for Order #{order_id}. "
        f"You'll pay when your order is delivered."
    )
    
    # Set payment status
    update_payment_status(order_id, "cash_on_delivery")
    
    # Proceed to shipping options
    return handle_shipping_options(business_context, user_id, order_id)

def handle_shipping_options(business_context, user_id, order_id):
    """Handle shipping options with business context"""
    logger.info(f"Handling shipping options for user {user_id}, order_id={order_id}, business={business_context.get('business_id')}")
    
    # Store in context
    set_last_context(user_id, {
        "action": "checkout",
        "order_id": order_id,
        "step": "shipping",
        "business_id": business_context.get('business_id')
    })
    
    # Present shipping options
    sections = []
    
    # Get saved addresses from database
    try:
        saved_addresses = get_customer_addresses(business_context, user_id)
        logger.info(f"Found {len(saved_addresses)} saved addresses for user {user_id}")
    except Exception as e:
        logger.error(f"Error fetching saved addresses: {str(e)}")
        saved_addresses = []
    
    # Add saved addresses section if available
    if saved_addresses:
        saved_addresses_rows = []
        for address in saved_addresses:
            address_display = f"{address.get('street', '')}, {address.get('city', '')}"
            saved_addresses_rows.append({
                "id": f"shipping_address_{address['id']}",
                "title": f"{address.get('name', 'Address')} - {'(Default)' if address.get('is_default', False) else ''}",
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
        business_context,
        user_id,
        "Choose Shipping Address",
        f"Order #{order_id} - How would you like to receive your order?",
        "Select Address",
        sections
    )
    
    # Set current action
    set_current_action(user_id, "awaiting_shipping_option")
    
    return True

def handle_shipping_selection(business_context, user_id, shipping_option):
    """Handle shipping address selection"""
    logger.info(f"Handling shipping selection for user {user_id}, option={shipping_option}, business={business_context.get('business_id')}")
    
    # Get order ID from context
    context = get_last_context(user_id)
    
    if not context or "order_id" not in context:
        send_text_message(business_context, user_id, "Sorry, there was a problem with your order. Please try again.")
        return False
    
    order_id = context["order_id"]
    
    # Handle different shipping options
    if shipping_option == "shipping_new_address":
        # Request location using the interactive location request message
        send_location_request_message(
            business_context,
            user_id,
            "Let us start with your delivery address. You can either manually *enter an address* or *share your current location*."
        )
        
        # Set action
        set_current_action(user_id, "awaiting_shipping_address_or_location")
        
    elif shipping_option == "shipping_location":
        # Request location
        send_location_request_message(
            business_context,
            user_id,
            "Please share your current location for delivery."
        )
        
        # Set action
        set_current_action(user_id, "awaiting_shipping_location")
        
    elif shipping_option.startswith("shipping_address_"):
        # Existing address selected
        address_id = shipping_option.replace("shipping_address_", "")
        return handle_existing_address_selection(business_context, user_id, order_id, address_id)
        
    else:
        send_text_message(business_context, user_id, "Sorry, that shipping option is not supported. Please choose another option.")
        return handle_shipping_options(business_context, user_id, order_id)
    
    return True

def handle_existing_address_selection(business_context, user_id, order_id, address_id):
    """Handle selection of an existing saved address"""
    try:
        # Get saved addresses from database
        saved_addresses = get_customer_addresses(business_context, user_id)
        
        # Find the selected address
        selected_address = None
        for address in saved_addresses:
            if str(address.get("id", "")) == str(address_id):
                selected_address = address
                break
        
        if not selected_address:
            send_text_message(business_context, user_id, "Sorry, we couldn't find that address. Please try again.")
            return False
        
        # Format the address
        formatted_address = (
            f"{selected_address.get('recipient', '')}\n"
            f"{selected_address.get('street', '')}\n"
            f"{selected_address.get('city', '')}, {selected_address.get('region', '')}\n"
            f"Phone: {selected_address.get('phone', '')}"
        )
        
        # Set shipping address
        set_shipping_address(order_id, formatted_address)
        
        # Complete the order
        return complete_order(business_context, user_id, order_id)
        
    except Exception as e:
        logger.error(f"Error handling existing address selection: {str(e)}")
        send_text_message(business_context, user_id, "Sorry, there was an error with your address selection. Please try again.")
        return False

def handle_location_message(business_context, user_id, message):
    """Handle location messages from WhatsApp"""
    try:
        logger.info(f"Received location message from {user_id}, business={business_context.get('business_id')}")
        
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
        
        try:
            geolocator = Nominatim(user_agent="whatsapp_store")
            location_info = geolocator.reverse(f"{latitude}, {longitude}", timeout=10)
            if location_info and location_info.address:
                location_text = str(location_info.address)
        except Exception as e:
            logger.warning(f"Error geocoding location: {str(e)}")
        
        # Update user session history
        update_session_history(user_id, "user", f"Shared location: {location_text}")
        
        # Check if we're waiting for a location for shipping
        current_action = get_current_action(user_id)
        
        if current_action == "awaiting_shipping_location" or current_action == "awaiting_shipping_address_or_location":
            # User shared location for shipping during checkout
            context = get_last_context(user_id)
            
            if not context or "order_id" not in context:
                send_text_message(business_context, user_id, "Sorry, there was a problem with your order. Please try again.")
                return False
            
            order_id = context["order_id"]
            business_id = business_context.get('business_id')
            
            # Save the location as an address in the database
            try:
                if hasattr(location_info, 'raw'):
                    address_id = save_customer_address(user_id, location_info.raw, "Location Address", business_id)
                    logger.info(f"Saved location as address {address_id}")
            except Exception as e:
                logger.warning(f"Could not save location as address: {str(e)}")
            
            # Set the formatted location as shipping address
            set_shipping_address(order_id, location_text)
            
            # Send confirmation message
            send_text_message(
                business_context,
                user_id,
                f"Thank you for sharing your location. Your order will be delivered to:\n\n{location_text}"
            )
            
            # Complete the order
            return complete_order(business_context, user_id, order_id)
        else:
            # User shared location but we weren't expecting it
            send_text_message(
                business_context,
                user_id,
                f"Thank you for sharing your location:\n\n{location_text}\n\nWould you like to save this as your delivery address for future orders?"
            )
            
            # Offer options
            buttons = [
                {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
            ]
            
            send_button_message(
                business_context,
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
            business_context,
            user_id, 
            "Sorry, there was a problem processing your location. Please try again or contact our support team."
        )
        return False

def handle_shipping_address(business_context, user_id, address_text):
    """Handle shipping address submission"""
    logger.info(f"Handling shipping address for user {user_id}, business={business_context.get('business_id')}")
    
    # Get order ID from context
    context = get_last_context(user_id)
    
    if not context or "order_id" not in context:
        send_text_message(business_context, user_id, "Sorry, there was a problem with your order. Please try again.")
        return False
    
    order_id = context["order_id"]
    
    # Set shipping address
    set_shipping_address(order_id, address_text)
    
    # Send confirmation
    send_text_message(
        business_context,
        user_id,
        f"Your order will be delivered to the following address:\n\n{address_text}"
    )
    
    # Complete order
    return complete_order(business_context, user_id, order_id)

def complete_order(business_context, user_id, order_id):
    """Complete the order process with business context"""
    try:
        logger.info(f"Completing order for user {user_id}, order_id={order_id}, business={business_context.get('business_id')}")
        business_id = business_context.get('business_id')
        
        # Get order details
        order = get_order_by_id(order_id)
        
        if not order:
            logger.error(f"Order {order_id} not found when completing")
            send_text_message(business_context, user_id, "❌ Sorry, there was an error with your order. Please contact support.")
            return False
        
        # Update order status to confirmed
        update_order_status(order_id, "confirmed")
        
        # Try to update customer's total orders count
        try:
            db = business_context.get('db')
            if db:
                from firebase_admin import firestore
                customers_ref = db.collection('customers')
                query = customers_ref.where('whatsapp_number', '==', user_id).where('business_id', '==', business_id)
                
                for doc in query.stream():
                    doc.reference.update({
                        'total_whatsapp_orders': firestore.FieldValue.increment(1),
                        'last_whatsapp_interaction': firestore.SERVER_TIMESTAMP
                    })
                    break
        except Exception as e:
            logger.warning(f"Could not update customer order count: {str(e)}")
        
        # Format order confirmation message
        from models.order import format_order_summary
        order_summary = format_order_summary(order_id)
        
        confirmation_message = (
            f"🎉 *Order Confirmed Successfully!*\n\n"
            f"{order_summary}\n\n"
            f"📧 You'll receive updates via WhatsApp as your order progresses.\n"
            f"📦 Estimated delivery: 3-5 business days\n\n"
            f"Thank you for shopping with us!"
        )
        
        # Send order management options
        buttons = [
            {"type": "reply", "reply": {"id": f"track_{order_id}", "title": "Track Order"}},
            {"type": "reply", "reply": {"id": "browse", "title": "Continue Shopping"}},
            {"type": "reply", "reply": {"id": "support", "title": "Get Help"}}
        ]
        
        send_button_message(
            business_context,
            user_id,
            "Order Management",
            confirmation_message,
            buttons
        )
        
        # Log analytics event
        try:
            db = business_context.get('db')
            if db:
                from firebase_admin import firestore
                analytics_data = {
                    'event_type': 'order_completed',
                    'user_id': user_id,
                    'business_id': business_id,
                    'metadata': {
                        'order_id': order_id,
                        'order_total': order.get('total', 0),
                        'item_count': order.get('item_count', 0),
                        'payment_method': order.get('payment_details', {}).get('method', 'unknown')
                    },
                    'created_at': firestore.SERVER_TIMESTAMP
                }
                db.collection('whatsapp_analytics').add(analytics_data)
        except Exception as e:
            logger.warning(f"Could not log analytics event: {str(e)}")
        
        # Clear current action and context
        set_current_action(user_id, None)
        set_last_context(user_id, {})
        
        logger.info(f"✅ Order {order_id} completed successfully for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error completing order {order_id} for user {user_id}: {str(e)}")
        
        # Send error message to user
        send_text_message(
            business_context,
            user_id,
            "❌ Sorry, there was an error completing your order. Our team has been notified. Please contact support if needed."
        )
        
        # Offer support options
        buttons = [
            {"type": "reply", "reply": {"id": "support", "title": "Contact Support"}},
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
        ]
        
        send_button_message(
            business_context,
            user_id,
            "Error",
            "How can we help you?",
            buttons
        )
        
        return False