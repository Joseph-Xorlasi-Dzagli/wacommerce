import requests
from utils.logger import get_logger
from datetime import datetime, timedelta
from firebase_admin import firestore

logger = get_logger(__name__)

# In-memory inventory cache per business
inventory_cache = {}
inventory_cache_updated = {}
CACHE_DURATION_MINUTES = 30

def get_cache_key(business_id, product_identifier):
    """Generate cache key for business-specific inventory"""
    return f"{business_id}_{product_identifier}"

def update_inventory_cache(business_context):
    """Refresh inventory data from Firebase for specific business"""
    business_id = business_context.get('business_id')
    db = business_context.get('db')
    
    if not business_id or not db:
        logger.error("Missing business_id or db in business context")
        return False
    
    try:
        inventory_ref = db.collection('inventory').where(
            filter=firestore.FieldFilter('business_id', '==', business_id)
        )
        inventory_docs = inventory_ref.get()
        
        business_cache = {}
        
        for doc in inventory_docs:
            inventory_data = doc.to_dict()
            # Cache by both product_id and product_option_id if they exist
            product_id = inventory_data.get('product_id')
            product_option_id = inventory_data.get('product_option_id')
            
            stock_data = {
                "stock_quantity": inventory_data.get('stock_quantity', 0),
                "stock_status": inventory_data.get('stock_status', 'out_of_stock'),
                "last_updated": inventory_data.get('last_updated', datetime.now()).isoformat(),
                "product_name": inventory_data.get('product_name', 'Unknown Product'),
                "product_option_id": product_option_id
            }
            
            if product_id:
                cache_key = get_cache_key(business_id, product_id)
                inventory_cache[cache_key] = stock_data
                
            if product_option_id:
                cache_key = get_cache_key(business_id, product_option_id)
                inventory_cache[cache_key] = stock_data
                    
                # Also cache by SKU if we can get it
                try:
                    option_ref = db.collection('product_options').document(product_option_id)
                    option_doc = option_ref.get()
                    if option_doc.exists:
                        sku = option_doc.to_dict().get('sku')
                        if sku:
                            cache_key = get_cache_key(business_id, sku)
                            inventory_cache[cache_key] = stock_data
                except:
                    pass
        
        inventory_cache_updated[business_id] = datetime.now()
        logger.info(f"Updated inventory cache for business {business_id} with {len(business_cache)} items")
        return True
        
    except Exception as e:
        logger.error(f"Error updating inventory cache for business {business_id}: {str(e)}")
        return False

def is_cache_valid(business_id):
    """Check if inventory cache is still valid for a business"""
    if business_id not in inventory_cache_updated:
        return False
    
    cache_age = datetime.now() - inventory_cache_updated[business_id]
    return cache_age < timedelta(minutes=CACHE_DURATION_MINUTES)

def get_stock_status(quantity):
    """Determine stock status based on quantity"""
    if quantity <= 0:
        return "out_of_stock"
    elif quantity <= 5:
        return "low_stock"
    else:
        return "in_stock"

def get_product_option_id_by_sku(business_context, sku):
    """Get product option ID from SKU for specific business"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db or not business_id:
        return None
    
    try:
        # Query product_options collection by SKU and business_id
        options_ref = db.collection('product_options').where(
            filter=firestore.FieldFilter('sku', '==', sku)
        ).where(
            filter=firestore.FieldFilter('business_id', '==', business_id)
        ).limit(1)
        
        options = options_ref.get()
        
        for option_doc in options:
            return option_doc.id  # Return the document ID (product option ID)
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting product option ID by SKU {sku} for business {business_id}: {str(e)}")
        return None

def get_product_stock(business_context, product_identifier):
    """Get current stock for a product using SKU, product option ID, or product ID"""
    business_id = business_context.get('business_id')
    db = business_context.get('db')
    
    # Update cache if it's stale
    if not is_cache_valid(business_id):
        update_inventory_cache(business_context)
    
    # Check cache first
    cache_key = get_cache_key(business_id, product_identifier)
    if cache_key in inventory_cache:
        return inventory_cache[cache_key]
    
    # Try to resolve SKU to product option ID first
    product_option_id = get_product_option_id_by_sku(business_context, product_identifier)
    
    if db and business_id:
        try:
            inventory_docs = None
            
            # If we found a product option ID, use it
            if product_option_id:
                inventory_ref = db.collection('inventory').where(
                    filter=firestore.FieldFilter('product_option_id', '==', product_option_id)
                ).where(
                    filter=firestore.FieldFilter('business_id', '==', business_id)
                ).limit(1)
                inventory_docs = inventory_ref.get()
            
            # If not found by product option, try as direct product_id
            if not inventory_docs:
                inventory_ref = db.collection('inventory').where(
                    filter=firestore.FieldFilter('product_id', '==', product_identifier)
                ).where(
                    filter=firestore.FieldFilter('business_id', '==', business_id)
                ).limit(1)
                inventory_docs = inventory_ref.get()
            
            # Process inventory data
            for doc in inventory_docs:
                inventory_data = doc.to_dict()
                
                # Get product name from product_options or products
                product_name = inventory_data.get('product_name', 'Unknown Product')
                if not product_name or product_name == 'Unknown Product':
                    try:
                        if product_option_id:
                            option_ref = db.collection('product_options').document(product_option_id)
                            option_doc = option_ref.get()
                            if option_doc.exists:
                                product_name = option_doc.to_dict().get('name', 'Unknown Product')
                        else:
                            product_ref = db.collection('products').document(product_identifier)
                            product_doc = product_ref.get()
                            if product_doc.exists:
                                product_data = product_doc.to_dict()
                                # Verify product belongs to this business
                                if product_data.get('business_id') == business_id:
                                    product_name = product_data.get('name', 'Unknown Product')
                    except:
                        pass
                
                stock_info = {
                    "stock_quantity": inventory_data.get('stock_quantity', 0),
                    "stock_status": inventory_data.get('stock_status', 'out_of_stock'),
                    "last_updated": inventory_data.get('last_updated', datetime.now()).isoformat(),
                    "product_name": product_name,
                    "product_option_id": product_option_id
                }
                
                # Cache by both original identifier and resolved ID
                cache_key = get_cache_key(business_id, product_identifier)
                inventory_cache[cache_key] = stock_info
                if product_option_id:
                    option_cache_key = get_cache_key(business_id, product_option_id)
                    inventory_cache[option_cache_key] = stock_info
                
                return stock_info
                
        except Exception as e:
            logger.error(f"Error fetching stock from Firebase for product {product_identifier} in business {business_id}: {str(e)}")
    
    # No inventory found - return out of stock
    logger.warning(f"No inventory data found for product {product_identifier} in business {business_id}, marking as out of stock")
    return {
        "stock_quantity": 0,
        "stock_status": "out_of_stock",
        "last_updated": datetime.now().isoformat(),
        "product_name": "Unknown Product",
        "product_option_id": product_option_id
    }

def check_inventory_availability(business_context, cart_items):
    """Main verification function to check cart items against inventory"""
    business_id = business_context.get('business_id')
    
    results = {
        "has_issues": False,
        "all_available": True,
        "issues": [],
        "modified_cart": [],
        "original_total": 0,
        "new_total": 0
    }
    
    try:
        for item in cart_items:
            product_id = item.get("product_id")
            requested_qty = item.get("quantity", 1)
            item_price = item.get("price", 0)
            
            # Get stock info
            stock_info = get_product_stock(business_context, product_id)
            available_qty = stock_info.get("stock_quantity", 0)
            
            # Calculate totals
            original_item_total = item_price * requested_qty
            results["original_total"] += original_item_total
            
            # Check availability
            if available_qty <= 0:
                # Out of stock
                results["has_issues"] = True
                results["all_available"] = False
                results["issues"].append({
                    "product_id": product_id,
                    "product_name": item.get("name", "Unknown Product"),
                    "issue_type": "out_of_stock",
                    "requested_qty": requested_qty,
                    "available_qty": 0,
                    "item_price": item_price
                })
                
            elif available_qty < requested_qty:
                # Insufficient stock
                results["has_issues"] = True
                results["issues"].append({
                    "product_id": product_id,
                    "product_name": item.get("name", "Unknown Product"),
                    "issue_type": "insufficient_stock",
                    "requested_qty": requested_qty,
                    "available_qty": available_qty,
                    "item_price": item_price
                })
                
                # Add available quantity to modified cart
                modified_item = item.copy()
                modified_item["quantity"] = available_qty
                results["modified_cart"].append(modified_item)
                
                new_item_total = item_price * available_qty
                results["new_total"] += new_item_total
                
            else:
                # Available as requested
                results["modified_cart"].append(item.copy())
                results["new_total"] += original_item_total
        
        logger.info(f"Inventory check completed for business {business_id}. Issues found: {results['has_issues']}")
        return results
        
    except Exception as e:
        logger.error(f"Error checking inventory availability for business {business_id}: {str(e)}")
        
        # Return safe fallback - assume all available
        return {
            "has_issues": False,
            "all_available": True,
            "issues": [],
            "modified_cart": cart_items.copy(),
            "original_total": sum(item.get("price", 0) * item.get("quantity", 1) for item in cart_items),
            "new_total": sum(item.get("price", 0) * item.get("quantity", 1) for item in cart_items)
        }

def format_inventory_message(inventory_results):
    """Format inventory check results into a user-friendly message"""
    if inventory_results["all_available"]:
        return None  # No message needed
    
    message = "⚠️ *Stock Availability Update*\n\n"
    message += "Some items in your cart have limited availability:\n\n"
    
    # Show issues
    for issue in inventory_results["issues"]:
        name = issue["product_name"]
        requested = issue["requested_qty"]
        available = issue["available_qty"]
        
        if issue["issue_type"] == "out_of_stock":
            message += f"❌ {name} - Out of stock (Requested: {requested}, Available: 0)\n"
        elif issue["issue_type"] == "insufficient_stock":
            message += f"⚠️ {name} - Limited stock (Requested: {requested}, Available: {available})\n"
    
    # Show items that are available
    available_items = []
    for item in inventory_results["modified_cart"]:
        available_items.append(f"✅ {item['name']} - Available (Requested: {item['quantity']})")
    
    if available_items:
        message += "\n" + "\n".join(available_items) + "\n"
    
    # Show modified order summary
    if inventory_results["modified_cart"]:
        message += "\n*Your order would be modified to:*\n"
        for item in inventory_results["modified_cart"]:
            item_total = item["price"] * item["quantity"]
            message += f"• {item['name']} x {item['quantity']} = GHS{item_total:.2f}\n"
        
        message += f"\n*New Total: GHS{inventory_results['new_total']:.2f}* "
        message += f"(Original: GHS{inventory_results['original_total']:.2f})\n\n"
    else:
        message += "\n*All requested items are currently out of stock.*\n\n"
    
    message += "Would you like to proceed with the available items or cancel your order?"
    
    return message

def update_cart_with_available_stock(business_context, user_id, modified_cart):
    """Update user's cart with only available stock quantities"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db or not business_id:
        logger.error("Missing db or business_id in business context")
        return False
    
    try:
        session_ref = db.collection('whatsapp_sessions').document(f"{business_id}_{user_id}")
        session_ref.update({
            'cart': modified_cart,
            'last_active': datetime.now()
        })
        
        logger.info(f"Updated cart for user {user_id} in business {business_id} with available stock quantities")
        return True
        
    except Exception as e:
        logger.error(f"Error updating cart with available stock for business {business_id}: {str(e)}")
        return False

def reserve_inventory(business_context, product_id, quantity):
    """Reserve inventory for a product during checkout"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db or not business_id:
        return False
    
    try:
        inventory_ref = db.collection('inventory').where(
            filter=firestore.FieldFilter('product_id', '==', product_id)
        ).where(
            filter=firestore.FieldFilter('business_id', '==', business_id)
        ).limit(1)
        inventory_docs = inventory_ref.get()
        
        for doc in inventory_docs:
            current_data = doc.to_dict()
            current_reserved = current_data.get('reserved_quantity', 0)
            
            # Update reserved quantity
            doc.reference.update({
                'reserved_quantity': current_reserved + quantity,
                'last_updated': datetime.now()
            })
            
            logger.info(f"Reserved {quantity} units of product {product_id} for business {business_id}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error reserving inventory for business {business_id}: {str(e)}")
        return False

def release_inventory(business_context, product_id, quantity):
    """Release reserved inventory for a product"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db or not business_id:
        return False
    
    try:
        inventory_ref = db.collection('inventory').where(
            filter=firestore.FieldFilter('product_id', '==', product_id)
        ).where(
            filter=firestore.FieldFilter('business_id', '==', business_id)
        ).limit(1)
        inventory_docs = inventory_ref.get()
        
        for doc in inventory_docs:
            current_data = doc.to_dict()
            current_reserved = current_data.get('reserved_quantity', 0)
            
            # Update reserved quantity (ensure it doesn't go below 0)
            new_reserved = max(0, current_reserved - quantity)
            
            doc.reference.update({
                'reserved_quantity': new_reserved,
                'last_updated': datetime.now()
            })
            
            logger.info(f"Released {quantity} units of product {product_id} for business {business_id}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error releasing inventory for business {business_id}: {str(e)}")
        return False

def update_stock_quantity(business_context, product_id, new_quantity, reason="manual_update"):
    """Update the actual stock quantity for a product"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db or not business_id:
        return False
    
    try:
        inventory_ref = db.collection('inventory').where(
            filter=firestore.FieldFilter('product_id', '==', product_id)
        ).where(
            filter=firestore.FieldFilter('business_id', '==', business_id)
        ).limit(1)
        inventory_docs = inventory_ref.get()
        
        for doc in inventory_docs:
            current_data = doc.to_dict()
            previous_quantity = current_data.get('stock_quantity', 0)
            
            # Update stock quantity and status
            new_status = get_stock_status(new_quantity)
            
            update_data = {
                'stock_quantity': new_quantity,
                'stock_status': new_status,
                'last_updated': datetime.now()
            }
            
            # Add to update history
            update_history = current_data.get('update_history', [])
            update_history.append({
                'previous_quantity': previous_quantity,
                'new_quantity': new_quantity,
                'reason': reason,
                'updated_by': 'system',
                'updated_at': datetime.now()
            })
            
            # Keep only last 10 updates
            if len(update_history) > 10:
                update_history = update_history[-10:]
            
            update_data['update_history'] = update_history
            
            doc.reference.update(update_data)
            
            # Update cache
            cache_key = get_cache_key(business_id, product_id)
            inventory_cache[cache_key] = {
                "stock_quantity": new_quantity,
                "stock_status": new_status,
                "last_updated": datetime.now().isoformat(),
                "product_name": current_data.get('product_name', 'Unknown Product')
            }
            
            logger.info(f"Updated stock quantity for product {product_id} in business {business_id} from {previous_quantity} to {new_quantity}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error updating stock quantity for business {business_id}: {str(e)}")
        return False