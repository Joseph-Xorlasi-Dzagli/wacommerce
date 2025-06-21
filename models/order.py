import uuid
from datetime import datetime
from models.session import init_user_session
from models.cart import get_cart, clear_cart, get_cart_total
from utils.logger import get_logger
from firebase_admin import firestore

logger = get_logger(__name__)

def create_order(business_context, user_id):
    """Create a new order from the user's cart with business context"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db or not business_id:
        logger.error("Missing db or business_id in business context")
        return None
    
    try:
        cart = get_cart(business_context, user_id)
        
        if not cart:
            logger.warning(f"Attempted to create order with empty cart for user {user_id} in business {business_id}")
            return None
        
        # Validate all cart items belong to this business
        for item in cart:
            item_business_id = item.get('business_id')
            if item_business_id and item_business_id != business_id:
                logger.error(f"Cart contains items from different business: {item_business_id} vs {business_id}")
                return None
        
        # Calculate total
        total = get_cart_total(business_context, user_id)
        
        # Generate order ID
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        
        # Get customer name from session if available
        from models.session import get_user_name
        customer_name = get_user_name(user_id) or "Customer"
        
        # Create order data
        order_data = {
            "business_id": business_id,
            "customer": {
                "whatsapp_number": user_id,
                "name": customer_name,
                "phone": user_id,
                "id": None  # Will be populated if customer exists in database
            },
            "source": "whatsapp",
            "whatsapp_session_id": f"{business_id}_{user_id}",
            "whatsapp_catalog_id": business_context.get('catalog_id', ''),
            "inventory_checked": False,
            "inventory_issues": [],
            "inventory_reserved": False,
            "status": "pending",
            "shipping_method": None,
            "shipping_address": None,
            "delivery_instructions": None,
            "city": None,
            "location": None,
            "structured_address": {},
            "subtotal": total,
            "shipping_fee": 0,
            "tax": 0,
            "total": total,
            "currency": "GHS",
            "payment_method": None,
            "payment_status": "pending",
            "payment_reference": None,
            "payment_details": {},
            "notes": "",
            "item_count": sum(item["quantity"] for item in cart),
            "tracking_number": None,
            "estimated_delivery": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "completed_at": None
        }
        
        # Try to get customer ID from database
        try:
            customers_ref = db.collection('customers')
            customer_query = customers_ref.where('whatsapp_number', '==', user_id).where('business_id', '==', business_id).limit(1)
            customer_docs = customer_query.get()
            
            for customer_doc in customer_docs:
                order_data["customer"]["id"] = customer_doc.id
                customer_data = customer_doc.to_dict()
                order_data["customer"]["name"] = customer_data.get('name', customer_name)
                break
        except Exception as e:
            logger.warning(f"Could not fetch customer data: {str(e)}")
        
        # Create order document
        order_ref = db.collection('orders').document(order_id)
        order_ref.set(order_data)
        
        # Create order items subcollection
        items_ref = order_ref.collection('items')
        for i, item in enumerate(cart):
            item_data = {
                "product_id": item["product_id"],
                "product_option_id": item.get("product_option_id", ""),
                "name": item["name"],
                "variant_details": "",  # Can be populated from product options
                "price": item["price"],
                "quantity": item["quantity"],
                "total": item["price"] * item["quantity"],
                "whatsapp_image_id": item.get("whatsapp_image_id", item.get("image_url", "")),
                "created_at": datetime.now()
            }
            
            # Add variant details if product option exists
            if item.get("product_option_id"):
                try:
                    option_ref = db.collection('product_options').document(item["product_option_id"])
                    option_doc = option_ref.get()
                    if option_doc.exists:
                        option_data = option_doc.to_dict()
                        attributes = option_data.get('attributes', {})
                        variant_details = []
                        for key, value in attributes.items():
                            if value:
                                variant_details.append(f"{key.title()}: {value}")
                        item_data["variant_details"] = ", ".join(variant_details)
                except Exception as e:
                    logger.warning(f"Could not fetch product option details: {str(e)}")
            
            items_ref.document(f"item_{i}").set(item_data)
        
        # Add order_id to the order data for return
        order_data["order_id"] = order_id
        
        logger.info(f"Created order {order_id} for user {user_id} in business {business_id}")
        
        # Clear cart after order creation
        clear_cart(business_context, user_id)
        
        return order_data
        
    except Exception as e:
        logger.error(f"Error creating order for business {business_id}: {str(e)}")
        return None

def get_user_orders(business_context, user_id):
    """Get all orders for a user within the current business context"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db or not business_id:
        return []
    
    try:
        orders_ref = db.collection('orders').where(
            filter=firestore.FieldFilter('customer.whatsapp_number', '==', user_id)
        ).where(
            filter=firestore.FieldFilter('business_id', '==', business_id)
        ).order_by('created_at', direction=firestore.Query.DESCENDING)
        
        orders = orders_ref.get()
        
        order_list = []
        for order in orders:
            order_data = order.to_dict()
            order_data["order_id"] = order.id
            order_list.append(order_data)
        
        return order_list
        
    except Exception as e:
        logger.error(f"Error getting user orders for business {business_id}: {str(e)}")
        return []

def get_order_by_id(order_id):
    """Get an order by its ID (business context will be validated by caller)"""
    # Note: This function doesn't take business_context because order_id should be unique
    # Business validation should be done by the caller
    try:
        # Try to get from environment first (for backward compatibility)
        from config import db
        if not db:
            logger.error("Firebase not initialized")
            return None
            
        order_ref = db.collection('orders').document(order_id)
        order_doc = order_ref.get()
        
        if order_doc.exists:
            order_data = order_doc.to_dict()
            order_data["order_id"] = order_id
            return order_data
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting order by ID {order_id}: {str(e)}")
        return None

def get_order_by_id_with_business_context(business_context, order_id):
    """Get an order by its ID with business context validation"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db or not business_id:
        return None
    
    try:
        order_ref = db.collection('orders').document(order_id)
        order_doc = order_ref.get()
        
        if order_doc.exists:
            order_data = order_doc.to_dict()
            
            # Validate order belongs to this business
            if order_data.get('business_id') != business_id:
                logger.warning(f"Order {order_id} does not belong to business {business_id}")
                return None
            
            order_data["order_id"] = order_id
            return order_data
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting order by ID for business {business_id}: {str(e)}")
        return None

def get_latest_order(business_context, user_id):
    """Get the user's most recent order within the current business context"""
    try:
        user_orders = get_user_orders(business_context, user_id)
        if not user_orders:
            return None
        
        # Orders are already sorted by created_at DESC, so return the first one
        return user_orders[0]
        
    except Exception as e:
        logger.error(f"Error getting latest order for business {business_context.get('business_id')}: {str(e)}")
        return None

def update_order_status(order_id, status):
    """Update an order's status"""
    try:
        from config import db
        if not db:
            return False
            
        order_ref = db.collection('orders').document(order_id)
        order_ref.update({
            'status': status,
            'updated_at': datetime.now()
        })
        
        # Add to order history
        add_order_note(order_id, f"Status changed to: {status}")
        
        logger.info(f"Updated order {order_id} status to {status}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating order status: {str(e)}")
        return False

def update_payment_status(order_id, status):
    """Update an order's payment status"""
    try:
        from config import db
        if not db:
            return False
            
        order_ref = db.collection('orders').document(order_id)
        order_ref.update({
            'payment_status': status,
            'updated_at': datetime.now()
        })
        
        # Add to order history
        add_order_note(order_id, f"Payment status changed to: {status}")
        
        logger.info(f"Updated order {order_id} payment status to {status}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating payment status: {str(e)}")
        return False

def set_shipping_address(order_id, address):
    """Set an order's shipping address"""
    try:
        from config import db
        if not db:
            return False
            
        order_ref = db.collection('orders').document(order_id)
        order_ref.update({
            'shipping_address': address,
            'updated_at': datetime.now()
        })
        
        # Try to parse structured address if it's a formatted string
        try:
            structured_address = parse_address_string(address)
            if structured_address:
                order_ref.update({'structured_address': structured_address})
        except Exception as e:
            logger.warning(f"Could not parse structured address: {str(e)}")
        
        # Add to order history
        add_order_note(order_id, "Shipping address updated")
        
        logger.info(f"Updated shipping address for order {order_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error setting shipping address: {str(e)}")
        return False

def set_shipping_method(order_id, method):
    """Set an order's shipping method"""
    try:
        from config import db
        if not db:
            return False
            
        order_ref = db.collection('orders').document(order_id)
        order_ref.update({
            'shipping_method': method,
            'updated_at': datetime.now()
        })
        
        # Add to order history
        add_order_note(order_id, f"Shipping method set to: {method}")
        
        logger.info(f"Updated shipping method for order {order_id} to {method}")
        return True
        
    except Exception as e:
        logger.error(f"Error setting shipping method: {str(e)}")
        return False

def set_tracking_number(order_id, tracking_number):
    """Set an order's tracking number"""
    try:
        from config import db
        if not db:
            return False
            
        order_ref = db.collection('orders').document(order_id)
        order_ref.update({
            'tracking_number': tracking_number,
            'updated_at': datetime.now()
        })
        
        # Add to order history
        add_order_note(order_id, f"Tracking number added: {tracking_number}")
        
        logger.info(f"Added tracking number for order {order_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error setting tracking number: {str(e)}")
        return False

def add_order_note(order_id, note):
    """Add a note to order history"""
    try:
        from config import db
        if not db:
            return False
            
        history_ref = db.collection('order_history')
        history_data = {
            "order_id": order_id,
            "status": note,
            "notes": note,
            "notification_sent": False,
            "created_by": "system",
            "created_at": datetime.now()
        }
        history_ref.add(history_data)
        return True
        
    except Exception as e:
        logger.error(f"Error adding order note: {str(e)}")
        return False

def format_order_summary(order_id):
    """Format a text summary of an order"""
    try:
        order = get_order_by_id(order_id)
        
        if not order:
            return "Order not found."
        
        summary = f"*Order #{order['order_id']}*\n"
        summary += f"*Status:* {order['status'].title()}\n"
        
        # Handle both datetime objects and strings
        created_at = order.get('created_at')
        if hasattr(created_at, 'strftime'):
            date_str = created_at.strftime('%Y-%m-%d')
        elif isinstance(created_at, str):
            date_str = created_at[:10]  # Take first 10 chars for date
        else:
            date_str = "Unknown"
            
        summary += f"*Date:* {date_str}\n"
        summary += f"*Payment:* {order['payment_status'].title()}\n\n"
        
        # Get order items from subcollection
        try:
            from config import db
            if db:
                items_ref = db.collection('orders').document(order_id).collection('items')
                items = items_ref.get()
                
                summary += "*Items:*\n"
                for item_doc in items:
                    item = item_doc.to_dict()
                    item_name = item.get('name', 'Unknown Item')
                    item_quantity = item.get('quantity', 1)
                    item_total = item.get('total', 0)
                    
                    # Add variant details if available
                    variant_details = item.get('variant_details', '')
                    if variant_details:
                        item_name += f" ({variant_details})"
                    
                    summary += f"• {item_name} x {item_quantity} = GHS{item_total:.2f}\n"
            else:
                summary += "*Items:* Unable to load items\n"
        except Exception as e:
            logger.error(f"Error loading order items: {str(e)}")
            summary += "*Items:* Error loading items\n"
        
        summary += f"\n*Total: GHS{order['total']:.2f}*\n\n"
        
        if order.get("shipping_address"):
            summary += f"*Shipping Address:*\n{order['shipping_address']}\n\n"
        
        if order.get("shipping_method"):
            summary += f"*Shipping Method:* {order['shipping_method']}\n"
        
        if order.get("tracking_number"):
            summary += f"*Tracking Number:* {order['tracking_number']}\n"
        
        return summary
        
    except Exception as e:
        logger.error(f"Error formatting order summary: {str(e)}")
        return "Error loading order summary."

def parse_address_string(address_string):
    """Parse a formatted address string into structured components"""
    if not address_string:
        return {}
    
    try:
        lines = address_string.strip().split('\n')
        structured = {}
        
        # Basic parsing - can be enhanced based on address format
        if len(lines) >= 1:
            structured['recipient'] = lines[0].strip()
        
        if len(lines) >= 2:
            structured['street'] = lines[1].strip()
        
        if len(lines) >= 3:
            # Try to parse "City, Region" format
            city_region = lines[2].strip()
            if ',' in city_region:
                parts = city_region.split(',')
                structured['city'] = parts[0].strip()
                if len(parts) > 1:
                    structured['region'] = parts[1].strip()
            else:
                structured['city'] = city_region
        
        # Look for phone number in any line
        for line in lines:
            if 'phone:' in line.lower() or 'tel:' in line.lower():
                phone_part = line.split(':')
                if len(phone_part) > 1:
                    structured['phone'] = phone_part[1].strip()
                break
        
        return structured
        
    except Exception as e:
        logger.error(f"Error parsing address string: {str(e)}")
        return {}

def get_business_orders(business_context, limit=50, status=None):
    """Get orders for a specific business with optional filtering"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db or not business_id:
        return []
    
    try:
        orders_ref = db.collection('orders').where(
            filter=firestore.FieldFilter('business_id', '==', business_id)
        ).order_by('created_at', direction=firestore.Query.DESCENDING).limit(limit)
        
        # Add status filter if provided
        if status:
            orders_ref = orders_ref.where(
                filter=firestore.FieldFilter('status', '==', status)
            )
        
        orders = orders_ref.get()
        
        order_list = []
        for order in orders:
            order_data = order.to_dict()
            order_data["order_id"] = order.id
            order_list.append(order_data)
        
        return order_list
        
    except Exception as e:
        logger.error(f"Error getting business orders: {str(e)}")
        return []

def get_order_analytics(business_context, start_date=None, end_date=None):
    """Get order analytics for a business within a date range"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db or not business_id:
        return {}
    
    try:
        orders_ref = db.collection('orders').where(
            filter=firestore.FieldFilter('business_id', '==', business_id)
        )
        
        # Add date filters if provided
        if start_date:
            orders_ref = orders_ref.where(
                filter=firestore.FieldFilter('created_at', '>=', start_date)
            )
        
        if end_date:
            orders_ref = orders_ref.where(
                filter=firestore.FieldFilter('created_at', '<=', end_date)
            )
        
        orders = orders_ref.get()
        
        # Calculate analytics
        total_orders = 0
        total_revenue = 0
        order_statuses = {}
        payment_methods = {}
        
        for order in orders:
            order_data = order.to_dict()
            total_orders += 1
            total_revenue += order_data.get('total', 0)
            
            # Count statuses
            status = order_data.get('status', 'unknown')
            order_statuses[status] = order_statuses.get(status, 0) + 1
            
            # Count payment methods
            payment_method = order_data.get('payment_method', 'unknown')
            payment_methods[payment_method] = payment_methods.get(payment_method, 0) + 1
        
        analytics = {
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'average_order_value': total_revenue / total_orders if total_orders > 0 else 0,
            'order_statuses': order_statuses,
            'payment_methods': payment_methods
        }
        
        return analytics
        
    except Exception as e:
        logger.error(f"Error getting order analytics: {str(e)}")
        return {}

def update_order_inventory_status(business_context, order_id, inventory_results):
    """Update order with inventory check results"""
    db = business_context.get('db')
    
    if not db:
        return False
    
    try:
        order_ref = db.collection('orders').document(order_id)
        order_ref.update({
            'inventory_checked': True,
            'inventory_issues': inventory_results.get('issues', []),
            'inventory_reserved': not inventory_results.get('has_issues', False),
            'updated_at': datetime.now()
        })
        
        # Add order note
        if inventory_results.get('has_issues', False):
            add_order_note(order_id, f"Inventory issues found: {len(inventory_results.get('issues', []))} items affected")
        else:
            add_order_note(order_id, "Inventory checked - all items available")
        
        logger.info(f"Updated order {order_id} inventory status")
        return True
        
    except Exception as e:
        logger.error(f"Error updating order inventory status: {str(e)}")
        return False

def cancel_order(business_context, order_id, reason="Customer request"):
    """Cancel an order and update all related data"""
    try:
        order = get_order_by_id_with_business_context(business_context, order_id)
        
        if not order:
            return False
        
        # Check if order can be cancelled
        if order.get('status') in ['delivered', 'shipped', 'cancelled']:
            logger.warning(f"Cannot cancel order {order_id} with status {order.get('status')}")
            return False
        
        # Update order status
        update_order_status(order_id, 'cancelled')
        
        # Release reserved inventory if any
        if order.get('inventory_reserved', False):
            try:
                # Get order items and release inventory
                db = business_context.get('db')
                if db:
                    items_ref = db.collection('orders').document(order_id).collection('items')
                    items = items_ref.get()
                    
                    from services.inventory import release_inventory
                    for item_doc in items:
                        item = item_doc.to_dict()
                        product_id = item.get('product_id')
                        quantity = item.get('quantity', 0)
                        if product_id and quantity > 0:
                            release_inventory(business_context, product_id, quantity)
            except Exception as e:
                logger.error(f"Error releasing inventory for cancelled order: {str(e)}")
        
        # Add cancellation note
        add_order_note(order_id, f"Order cancelled: {reason}")
        
        logger.info(f"Successfully cancelled order {order_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error cancelling order {order_id}: {str(e)}")
        return False

def migrate_order_to_business_context(order_id, business_id):
    """Migrate an existing order to include business context"""
    try:
        from config import db
        if not db:
            return False
            
        order_ref = db.collection('orders').document(order_id)
        order_doc = order_ref.get()
        
        if order_doc.exists:
            order_data = order_doc.to_dict()
            
            # Add business_id if not present
            if 'business_id' not in order_data:
                order_ref.update({
                    'business_id': business_id,
                    'updated_at': datetime.now()
                })
                
                logger.info(f"Migrated order {order_id} to business {business_id}")
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error migrating order to business context: {str(e)}")
        return False