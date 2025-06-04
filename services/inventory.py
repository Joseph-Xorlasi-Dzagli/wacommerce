import requests
from config import WHATSAPP_TOKEN, CATALOG_ID, product_cache
from services.catalog import get_product_by_id
from utils.logger import get_logger
from datetime import datetime, timedelta
from config import MOCK_INVENTORY_DATA


logger = get_logger(__name__)

# In-memory inventory cache
inventory_cache = {}
inventory_cache_updated = None
CACHE_DURATION_MINUTES = 30

def update_inventory_cache():
    """Refresh inventory data from WhatsApp Business API"""
    global inventory_cache_updated
    
    if not CATALOG_ID:
        logger.error("No catalog ID available for inventory check")
        return False
    
    try:
        url = f"https://graph.facebook.com/v22.0/{CATALOG_ID}/products"
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        params = {
            "fields": "id,retailer_id,inventory,name"
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch inventory data: {response.text}")
            return False
        
        data = response.json()
        products = data.get("data", [])
        
    
        # Update inventory cache
        for product in products:
            product_id = product.get("id")
            retailer_id = product.get("retailer_id")
            print(f"Processing product: {product.get('name', 'Unknown')} product_id: {product_id}")


            mock_data = MOCK_INVENTORY_DATA.get(product_id)

            # if mock_data:
            inventory_data = {
                "stock_quantity": mock_data.get("stock_quantity", 0) if mock_data else 0,
                "stock_status": mock_data.get("stock_status", get_stock_status(mock_data.get("stock_quantity", 0) if mock_data else 0)) if mock_data else "out_of_stock",
                "last_updated": datetime.now().isoformat(),
                "product_name": product.get("name", "Unknown Product")
            }

            
            if product_id:
                inventory_cache[product_id] = inventory_data
            if retailer_id:
                inventory_cache[retailer_id] = inventory_data
        
        inventory_cache_updated = datetime.now()
        logger.info(f"Updated inventory cache with {len(products)} products")
        return True
        
    except Exception as e:
        logger.error(f"Error updating inventory cache: {str(e)}")
        return False

def get_stock_status(quantity):
    """Determine stock status based on quantity"""
    if quantity <= 0:
        return "out_of_stock"
    elif quantity <= 5:
        return "low_stock"
    else:
        return "in_stock"

def is_cache_valid():
    """Check if inventory cache is still valid"""
    if not inventory_cache_updated:
        return False
    
    cache_age = datetime.now() - inventory_cache_updated
    return cache_age < timedelta(minutes=CACHE_DURATION_MINUTES)

def get_product_stock(product_id):
    """Get current stock for a product"""
    # Update cache if it's stale
    if not is_cache_valid():
        update_inventory_cache()
    
    # Check cache first
    if product_id in inventory_cache:
        return inventory_cache[product_id]
    
    # If not in cache, try to fetch individual product
    try:
        product = get_product_by_id(product_id)
        if product and "inventory" in product:
            # Try to get mock inventory data from config.py if available
            mock_data = MOCK_INVENTORY_DATA.get(product_id)
            # if mock_data:
            inventory_data = {
                "stock_quantity": mock_data.get("stock_quantity", 0),
                "stock_status": mock_data.get("stock_status", get_stock_status(mock_data.get("stock_quantity", 0))),
                "last_updated": datetime.now().isoformat(),
                "product_name": product.get("name", "Unknown Product")
            }
            # else:
            #     inventory_data = {
            #         "stock_quantity": product["inventory"],
            #         "stock_status": get_stock_status(product["inventory"]),
            #         "last_updated": datetime.now().isoformat(),
            #         "product_name": product.get("name", "Unknown Product")
            #     }
            
            # Update cache
            inventory_cache[product_id] = inventory_data
            return inventory_data
    except Exception as e:
        logger.error(f"Error fetching stock for product {product_id}: {str(e)}")
    
    # Default fallback - assume available but log warning
    logger.warning(f"No inventory data found for product {product_id}, assuming available")
    return {
        "stock_quantity": 999,  # Large number to indicate "available"
        "stock_status": "in_stock",
        "last_updated": datetime.now().isoformat(),
        "product_name": "Unknown Product"
    }

def check_inventory_availability(cart_items):
    """Main verification function to check cart items against inventory"""
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
            stock_info = get_product_stock(product_id)
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
                # Don't add to modified cart
                
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
        
        logger.info(f"Inventory check completed. Issues found: {results['has_issues']}")
        return results
        
    except Exception as e:
        logger.error(f"Error checking inventory availability: {str(e)}")
        
        # Return safe fallback - assume all available
        return {
            "has_issues": False,
            "all_available": True,
            "issues": [],
            "modified_cart": cart_items.copy(),
            "original_total": sum(item.get("price", 0) * item.get("quantity", 1) for item in cart_items),
            "new_total": sum(item.get("price", 0) * item.get("quantity", 1) for item in cart_items)
        }

def calculate_availability_changes(cart_items):
    """Determine what adjustments are needed - wrapper for main check function"""
    return check_inventory_availability(cart_items)

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

def update_cart_with_available_stock(user_id, modified_cart):
    """Update user's cart with only available stock quantities"""
    from models.session import init_user_session
    
    session = init_user_session(user_id)
    session["cart"] = modified_cart.copy()
    
    logger.info(f"Updated cart for user {user_id} with available stock quantities")
    return True