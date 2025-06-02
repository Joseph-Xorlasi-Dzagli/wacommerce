import json
from models.order import get_user_orders, get_order_by_id, get_latest_order, format_order_summary
from models.session import set_current_action, get_current_action, update_session_history
from services.messenger import send_text_message, send_button_message, send_list_message
from utils.logger import get_logger

logger = get_logger(__name__)

def handle_order_status(user_id, order_id=None):
    """Handle order status query"""
    logger.info(f"Handling order status for user {user_id}, order_id={order_id}")
    
    # If no specific order ID, show recent orders
    if not order_id:
        return handle_show_orders(user_id)
    
    # Get order details
    order = get_order_by_id(order_id)
    
    if not order or order['user_id'] != user_id:
        send_text_message(user_id, "Sorry, I couldn't find that order. Please check the order number and try again.")
        return False
    
    # Format order summary
    order_summary = format_order_summary(order_id)
    
    # Send order status
    send_text_message(user_id, order_summary)
    
    # Order actions
    buttons = []
    
    if order["status"] in ["confirmed", "processing", "shipped"]:
        buttons.append({"type": "reply", "reply": {"id": f"track_{order_id}", "title": "Track Order"}})
    
    if order["status"] in ["confirmed", "processing"]:
        buttons.append({"type": "reply", "reply": {"id": f"cancel_{order_id}", "title": "Cancel Order"}})
    
    buttons.append({"type": "reply", "reply": {"id": "support", "title": "Need Help?"}})
    
    send_button_message(
        user_id,
        "Order Options",
        "What would you like to do?",
        buttons
    )
    
    return True

def handle_show_orders(user_id):
    """Show the user's recent orders"""
    logger.info(f"Handling show orders for user {user_id}")
    
    # Get user orders
    orders = get_user_orders(user_id)
    
    if not orders or len(orders) == 0:
        send_text_message(user_id, "You don't have any orders yet. Would you like to browse our products?")
        
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
        ]
        
        send_button_message(user_id, "No Orders", "Start shopping?", buttons)
        return True
    
    # Sort by date, most recent first
    sorted_orders = sorted(orders, key=lambda x: x["created_at"], reverse=True)
    
    # If only one order, show its details
    if len(sorted_orders) == 1:
        return handle_order_status(user_id, sorted_orders[0]["order_id"])
    
    # Multiple orders, show list
    rows = []
    for order in sorted_orders[:10]:  # Limit to 10 most recent
        rows.append({
            "id": f"order_{order['order_id']}",
            "title": f"Order #{order['order_id']}",
            "description": f"Status: {order['status'].title()} - Date: {order['created_at'][:10]}"
        })
    
    sections = [{
        "title": "Your Recent Orders",
        "rows": rows
    }]
    
    send_list_message(
        user_id,
        "Order History",
        "Select an order to view details:",
        "View Order",
        sections
    )
    
    return True

def handle_track_order(user_id, order_id):
    """Handle tracking an order"""
    logger.info(f"Handling track order for user {user_id}, order_id={order_id}")
    
    # Get order details
    order = get_order_by_id(order_id)
    
    if not order or order['user_id'] != user_id:
        send_text_message(user_id, "Sorry, I couldn't find that order. Please check the order number and try again.")
        return False
    
    # Different messages based on order status
    tracking_info = ""
    
    if order["status"] == "confirmed":
        tracking_info = (
            f"*Order #{order_id} - Confirmed*\n\n"
            f"Your order has been confirmed and is being prepared. "
            f"You'll receive a tracking number once it ships."
        )
    elif order["status"] == "processing":
        tracking_info = (
            f"*Order #{order_id} - Processing*\n\n"
            f"Your order is being processed and packed. "
            f"Estimated shipping date: {get_estimated_ship_date(order)}"
        )
    elif order["status"] == "shipped":
        tracking_info = (
            f"*Order #{order_id} - Shipped*\n\n"
            f"Your order has been shipped and is on its way to you!\n"
        )
        
        if "tracking_number" in order and order["tracking_number"]:
            tracking_info += f"*Tracking Number:* {order['tracking_number']}\n"
            tracking_info += f"*Carrier:* Example Shipping\n"
            tracking_info += f"*Tracking Link:* https://example.com/track/{order['tracking_number']}\n"
            tracking_info += f"\nEstimated delivery date: {get_estimated_delivery_date(order)}"
        else:
            tracking_info += (
                f"Your tracking number will be available soon. "
                f"Estimated delivery date: {get_estimated_delivery_date(order)}"
            )
    elif order["status"] == "delivered":
        tracking_info = (
            f"*Order #{order_id} - Delivered*\n\n"
            f"Your order has been delivered. We hope you enjoy your purchase!"
        )
    elif order["status"] == "cancelled":
        tracking_info = (
            f"*Order #{order_id} - Cancelled*\n\n"
            f"This order has been cancelled."
        )
    else:
        tracking_info = (
            f"*Order #{order_id} - {order['status'].title()}*\n\n"
            f"Status: {order['status'].title()}\n"
            f"Date: {order['created_at'][:10]}"
        )
    
    send_text_message(user_id, tracking_info)
    
    # Offer help options
    buttons = [
        {"type": "reply", "reply": {"id": f"track_{order_id}", "title": "Track Order"}},
        {"type": "reply", "reply": {"id": "browse", "title": "Continue Shopping"}}
    ]
    
    send_button_message(
        user_id,
        "Order Tracking",
        "What would you like to do next?",
        buttons
    )
    
    return True

def handle_cancel_order(user_id, order_id):
    """Handle cancelling an order"""
    logger.info(f"Handling cancel order for user {user_id}, order_id={order_id}")
    
    # Get order details
    order = get_order_by_id(order_id)
    
    if not order or order['user_id'] != user_id:
        send_text_message(user_id, "Sorry, I couldn't find that order. Please check the order number and try again.")
        return False
    
    # Check if order can be cancelled
    if order["status"] not in ["confirmed", "processing"]:
        send_text_message(
            user_id, 
            f"Sorry, order #{order_id} cannot be cancelled because it has already been {order['status']}."
        )
        return False
    
    # Confirm cancellation
    confirmation_message = (
        f"Are you sure you want to cancel order #{order_id}?\n\n"
        f"This action cannot be undone, and any payment will be refunded according to our refund policy."
    )
    
    buttons = [
        {"type": "reply", "reply": {"id": f"confirm_cancel_{order_id}", "title": "Yes, Cancel Order"}},
        {"type": "reply", "reply": {"id": f"order_{order_id}", "title": "No, Keep Order"}}
    ]
    
    send_button_message(
        user_id,
        "Confirm Cancellation",
        confirmation_message,
        buttons
    )
    
    return True

def handle_confirm_cancel_order(user_id, order_id):
    """Handle confirmed order cancellation"""
    logger.info(f"Handling confirmed cancel order for user {user_id}, order_id={order_id}")
    
    # Get order details
    order = get_order_by_id(order_id)
    
    if not order or order['user_id'] != user_id:
        send_text_message(user_id, "Sorry, I couldn't find that order. Please check the order number and try again.")
        return False
    
    # Update order status
    from models.order import update_order_status, add_order_note
    update_order_status(order_id, "cancelled")
    add_order_note(order_id, f"Order cancelled by customer via WhatsApp")
    
    # Send confirmation
    send_text_message(
        user_id,
        f"Order #{order_id} has been cancelled. If you made a payment, it will be refunded according to our refund policy."
    )
    
    # Offer to browse products
    buttons = [
        {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}},
        {"type": "reply", "reply": {"id": "support", "title": "Need Help?"}}
    ]
    
    send_button_message(
        user_id,
        "Order Cancelled",
        "What would you like to do next?",
        buttons
    )
    
    return True

def get_estimated_ship_date(order):
    """Calculate estimated shipping date based on order date"""
    from datetime import datetime, timedelta
    
    # Parse order date
    try:
        order_date = datetime.fromisoformat(order["created_at"])
        # Add 1-2 business days for processing
        ship_date = order_date + timedelta(days=2)
        return ship_date.strftime("%Y-%m-%d")
    except Exception:
        return "soon"

def get_estimated_delivery_date(order):
    """Calculate estimated delivery date based on order date and shipping method"""
    from datetime import datetime, timedelta
    
    # Parse order date
    try:
        order_date = datetime.fromisoformat(order["created_at"])
        
        # Different delivery times based on shipping method
        if order.get("shipping_method", "").lower().startswith("express"):
            # Express shipping: 1-2 days after shipping (which is 1-2 days after order)
            delivery_date = order_date + timedelta(days=4)
        else:
            # Standard shipping: 3-5 days after shipping (which is 1-2 days after order)
            delivery_date = order_date + timedelta(days=7)
            
        return delivery_date.strftime("%Y-%m-%d")
    except Exception:
        return "within 7-10 business days"
    

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