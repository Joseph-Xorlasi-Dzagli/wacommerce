import json
from models.order import get_user_orders, get_order_by_id, format_order_summary
from models.session import update_session_history
from models.cart import clear_cart, add_to_cart_with_details
from services.messenger import send_text_message, send_button_message, send_list_message
from utils.logger import get_logger

logger = get_logger(__name__)

def handle_order_status(business_context, user_id, order_id=None):
    """Handle order status query with business context"""
    logger.info(f"Handling order status for user {user_id}, order_id={order_id}, business={business_context.get('business_id')}")
    
    # If no specific order ID, show recent orders
    if not order_id:
        return handle_show_orders(business_context, user_id)
    
    # Get order details
    order = get_order_by_id(order_id)
    
    # Verify order belongs to this user and business
    if not order or order['customer']['whatsapp_number'] != user_id:
        send_text_message(business_context, user_id, "Sorry, I couldn't find that order. Please check the order number and try again.")
        return False
    
    # Additional business context validation
    if order.get('business_id') != business_context.get('business_id'):
        send_text_message(business_context, user_id, "Sorry, I couldn't find that order. Please check the order number and try again.")
        return False
    
    # Format order summary
    order_summary = format_order_summary(order_id)
    
    # Send order status
    send_text_message(business_context, user_id, order_summary)
    
    # Order actions
    buttons = []
    
    if order["status"] in ["confirmed", "processing", "shipped"]:
        buttons.append({"type": "reply", "reply": {"id": f"track_{order_id}", "title": "Track Order"}})
    
    if order["status"] in ["confirmed", "processing"]:
        buttons.append({"type": "reply", "reply": {"id": f"cancel_{order_id}", "title": "Cancel Order"}})
    
    buttons.append({"type": "reply", "reply": {"id": "support", "title": "Need Help?"}})
    
    send_button_message(
        business_context,
        user_id,
        "Order Options",
        "What would you like to do?",
        buttons
    )
    
    return True

def handle_show_orders(business_context, user_id):
    """Show the user's recent orders with business context"""
    logger.info(f"Handling show orders for user {user_id}, business={business_context.get('business_id')}")
    
    # Get user orders for this business
    orders = get_user_orders(business_context, user_id)
    
    if not orders or len(orders) == 0:
        send_text_message(business_context, user_id, "You don't have any orders yet. Would you like to browse our products?")
        
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
        ]
        
        send_button_message(business_context, user_id, "No Orders", "Start shopping?", buttons)
        return True
    
    # Sort by date, most recent first
    try:
        sorted_orders = sorted(orders, key=lambda x: x["created_at"], reverse=True)
    except Exception as e:
        logger.error(f"Error sorting orders: {str(e)}")
        sorted_orders = orders
    
    # If only one order, show its details
    if len(sorted_orders) == 1:
        return handle_order_status(business_context, user_id, sorted_orders[0]["order_id"])
    
    # Multiple orders, show list
    rows = []
    for order in sorted_orders[:10]:  # Limit to 10 most recent
        try:
            created_date = order['created_at']
            if hasattr(created_date, 'strftime'):
                date_str = created_date.strftime('%Y-%m-%d')
            else:
                date_str = str(created_date)[:10]
        except:
            date_str = "Unknown"
            
        rows.append({
            "id": f"order_{order['order_id']}",
            "title": f"Order #{order['order_id']}",
            "description": f"Status: {order['status'].title()} - Date: {date_str}"
        })
    
    sections = [{
        "title": "Your Recent Orders",
        "rows": rows
    }]
    
    send_list_message(
        business_context,
        user_id,
        "Order History",
        "Select an order to view details:",
        "View Order",
        sections
    )
    
    return True

def handle_order_message(business_context, user_id, message):
    """Handle order messages from WhatsApp with business context"""
    try:
        logger.info(f"Received order message from {user_id}, business={business_context.get('business_id')}")
        
        # Extract order data
        order_data = message.get("order", {})
        catalog_id = order_data.get("catalog_id", "")
        order_text = order_data.get("text", "")
        product_items = order_data.get("product_items", [])
        
        # Verify catalog belongs to this business
        business_catalog_id = business_context.get('catalog_id')
        if catalog_id != business_catalog_id:
            logger.warning(f"Order catalog ID {catalog_id} doesn't match business catalog {business_catalog_id}")
            send_text_message(
                business_context,
                user_id, 
                "Sorry, there was a problem processing your order. The products may not be available."
            )
            return False
        
        # Log order details
        logger.info(f"Order details - Catalog: {catalog_id}, Text: {order_text}")
        logger.info(f"Order products: {json.dumps(product_items)}")
        
        # Update user session history
        update_session_history(user_id, "user", f"Placed an order with {len(product_items)} item(s)")
        
        # Initialize cart with ordered items
        clear_cart(business_context, user_id)
        
        # Add items to cart
        total_items = 0 
        for item in product_items:
            product_id = item.get("product_retailer_id", "")
            quantity = item.get("quantity", 1)
            
            # Get item price and currency
            item_price = item.get("item_price", 0)
            currency = item.get("currency", "GHS")
            
            # Add to cart with provided details
            success = add_to_cart_with_details(
                business_context,
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
        handle_confirm_checkout(business_context, user_id)
        
        return True
    except Exception as e:
        logger.error(f"Error processing order message for business {business_context.get('business_id')}: {str(e)}")
        
        # Send error message to user
        send_text_message(
            business_context,
            user_id, 
            "Sorry, there was a problem processing your order. Please try again or contact our support team."
        )
        return False