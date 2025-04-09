import uuid
from datetime import datetime
from models.session import init_user_session
from models.cart import get_cart, clear_cart, get_cart_total
from config import orders
from utils.logger import get_logger

logger = get_logger(__name__)

def create_order(user_id):
    """Create a new order from the user's cart"""
    cart = get_cart(user_id)
    
    if not cart:
        logger.warning(f"Attempted to create order with empty cart for user {user_id}")
        return None
    
    # Calculate total
    total = get_cart_total(user_id)
    
    # Generate order ID
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    # Create order
    order = {
        "order_id": order_id,
        "user_id": user_id,
        "items": cart.copy(),
        "total": total,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "payment_status": "pending",
        "shipping_address": None,
        "shipping_method": None,
        "tracking_number": None,
        "notes": []
    }
    
    orders.append(order)
    logger.info(f"Created order {order_id} for user {user_id}")
    
    # Clear cart after order creation
    clear_cart(user_id)
    
    return order

def get_user_orders(user_id):
    """Get all orders for a user"""
    user_orders = [order for order in orders if order["user_id"] == user_id]
    return user_orders

def get_order_by_id(order_id):
    """Get an order by its ID"""
    order = next((order for order in orders if order["order_id"] == order_id), None)
    return order

def get_latest_order(user_id):
    """Get the user's most recent order"""
    user_orders = get_user_orders(user_id)
    if not user_orders:
        return None
    
    # Sort by created_at (descending) and get the first order
    sorted_orders = sorted(user_orders, key=lambda x: x["created_at"], reverse=True)
    return sorted_orders[0]

def update_order_status(order_id, status):
    """Update an order's status"""
    order = get_order_by_id(order_id)
    if order:
        order["status"] = status
        order["updated_at"] = datetime.now().isoformat()
        
        # Add a note about the status change
        add_order_note(order_id, f"Status changed to: {status}")
        
        logger.info(f"Updated order {order_id} status to {status}")
        return True
    
    logger.warning(f"Failed to update status for order {order_id} - not found")
    return False

def update_payment_status(order_id, status):
    """Update an order's payment status"""
    order = get_order_by_id(order_id)
    if order:
        order["payment_status"] = status
        order["updated_at"] = datetime.now().isoformat()
        
        # Add a note about the payment status change
        add_order_note(order_id, f"Payment status changed to: {status}")
        
        logger.info(f"Updated order {order_id} payment status to {status}")
        return True
    
    logger.warning(f"Failed to update payment status for order {order_id} - not found")
    return False

def set_shipping_address(order_id, address):
    """Set an order's shipping address"""
    order = get_order_by_id(order_id)
    if order:
        order["shipping_address"] = address
        order["updated_at"] = datetime.now().isoformat()
        
        # Add a note about the address update
        add_order_note(order_id, "Shipping address updated")
        
        logger.info(f"Updated shipping address for order {order_id}")
        return True
    
    logger.warning(f"Failed to update shipping address for order {order_id} - not found")
    return False

def set_shipping_method(order_id, method):
    """Set an order's shipping method"""
    order = get_order_by_id(order_id)
    if order:
        order["shipping_method"] = method
        order["updated_at"] = datetime.now().isoformat()
        
        # Add a note about the shipping method update
        add_order_note(order_id, f"Shipping method set to: {method}")
        
        logger.info(f"Updated shipping method for order {order_id} to {method}")
        return True
    
    logger.warning(f"Failed to update shipping method for order {order_id} - not found")
    return False

def set_tracking_number(order_id, tracking_number):
    """Set an order's tracking number"""
    order = get_order_by_id(order_id)
    if order:
        order["tracking_number"] = tracking_number
        order["updated_at"] = datetime.now().isoformat()
        
        # Add a note about the tracking number
        add_order_note(order_id, f"Tracking number added: {tracking_number}")
        
        logger.info(f"Added tracking number for order {order_id}")
        return True
    
    logger.warning(f"Failed to add tracking number for order {order_id} - not found")
    return False

def add_order_note(order_id, note):
    """Add a note to an order"""
    order = get_order_by_id(order_id)
    if order:
        order["notes"].append({
            "text": note,
            "timestamp": datetime.now().isoformat()
        })
        return True
    return False

def format_order_summary(order_id):
    """Format a text summary of an order"""
    order = get_order_by_id(order_id)
    
    if not order:
        return "Order not found."
    
    summary = f"*Order #{order['order_id']}*\n"
    summary += f"*Status:* {order['status'].title()}\n"
    summary += f"*Date:* {order['created_at'][:10]}\n"
    summary += f"*Payment:* {order['payment_status'].title()}\n\n"
    
    summary += "*Items:*\n"
    for item in order['items']:
        item_total = item["price"] * item["quantity"]
        summary += f"• {item['name']} x {item['quantity']} = ${item_total:.2f}\n"
    
    summary += f"\n*Total: ${order['total']:.2f}*\n\n"
    
    if order["shipping_address"]:
        summary += f"*Shipping Address:*\n{order['shipping_address']}\n\n"
    
    if order["shipping_method"]:
        summary += f"*Shipping Method:* {order['shipping_method']}\n"
    
    if order["tracking_number"]:
        summary += f"*Tracking Number:* {order['tracking_number']}\n"
    
    return summary