from models.session import init_user_session
from services.catalog import get_product_by_id, get_product_by_retailer_id
from utils.logger import get_logger
from datetime import datetime

logger = get_logger(__name__)

def get_cart(business_context, user_id):
    """Get the user's current shopping cart with business context"""
    try:
        db = business_context.get('db')
        business_id = business_context.get('business_id')
        
        if db and business_id:
            # Get cart from Firebase
            session_ref = db.collection('whatsapp_sessions').document(f"{business_id}_{user_id}")
            session_doc = session_ref.get()
            
            if session_doc.exists:
                return session_doc.to_dict().get('cart', [])
            else:
                # Initialize empty cart in Firebase
                session_ref.set({
                    'cart': [],
                    'user_id': user_id,
                    'business_id': business_id,
                    'created_at': datetime.now(),
                    'last_active': datetime.now()
                })
                return []
        else:
            # Fallback to in-memory session
            session = init_user_session(user_id)
            return session.get("cart", [])
            
    except Exception as e:
        logger.error(f"Error getting cart for business {business_context.get('business_id')}: {str(e)}")
        return []

def add_to_cart(business_context, user_id, product_id, quantity=1):
    """Add a product to the user's cart with business context"""
    try:
        # Get product details with business context
        product = get_product_by_id(business_context, product_id)
        
        if not product:
            logger.error(f"Failed to add product {product_id} to cart - product not found")
            return False
        
        # Verify product belongs to this business
        if product.get('business_id') != business_context.get('business_id'):
            logger.error(f"Product {product_id} does not belong to business {business_context.get('business_id')}")
            return False
        
        return add_to_cart_with_details(
            business_context,
            user_id, 
            product_id, 
            quantity,
            price=product.get("price", 0),
            currency=product.get("currency", "GHS")
        )
        
    except Exception as e:
        logger.error(f"Error adding to cart for business {business_context.get('business_id')}: {str(e)}")
        return False

def add_to_cart_with_details(business_context, user_id, product_identifier, quantity=1, price=None, currency=None):
    """Add a product to the user's cart with specific price details and business context"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db or not business_id:
        logger.error("Missing db or business_id in business context")
        return False
    
    try:
        session_ref = db.collection('whatsapp_sessions').document(f"{business_id}_{user_id}")
        session_doc = session_ref.get()
        
        if session_doc.exists:
            current_cart = session_doc.to_dict().get('cart', [])
        else:
            current_cart = []
            # Initialize session
            session_ref.set({
                'cart': [],
                'user_id': user_id,
                'business_id': business_id,
                'created_at': datetime.now(),
                'last_active': datetime.now()
            })
        
        # Resolve SKU to product option ID if needed
        from services.inventory import get_product_option_id_by_sku
        product_option_id = get_product_option_id_by_sku(business_context, product_identifier)
        
        # Get product details if price not provided
        product_name = ""
        product_image_url = ""
        
        if price is None:
            # Get product details from catalog with business context
            product = get_product_by_retailer_id(business_context, product_identifier)
            if not product:
                logger.error(f"Failed to add product {product_identifier} to cart - product not found")
                return False
            
            # Verify product belongs to this business
            if product.get('business_id') != business_id:
                logger.error(f"Product {product_identifier} does not belong to business {business_id}")
                return False
            
            # Get price from product
            price = product.get("price", "0")
            if isinstance(price, str) and ' ' in price:
                # Handle price format like "10 GHS"
                price = price.split()[0]
            
            product_name = product.get("name", f"Product {product_identifier}")
            product_image_url = product.get("whatsapp_image_url", product.get("image_url", ""))
            currency = product.get("currency", currency or "GHS")
        else:
            # If we don't have product details but have the ID, try to get minimal info
            try:
                if product_option_id:
                    # Get name from product_options collection
                    option_ref = db.collection('product_options').document(product_option_id)
                    option_doc = option_ref.get()
                    if option_doc.exists:
                        option_data = option_doc.to_dict()
                        # Verify belongs to this business
                        if option_data.get('business_id') == business_id:
                            product_name = option_data.get("name", f"Product {product_identifier}")
                            product_image_url = option_data.get("whatsapp_image_url", "")
                else:
                    # Get from products collection
                    product = get_product_by_retailer_id(business_context, product_identifier)
                    if product and product.get('business_id') == business_id:
                        product_name = product.get("name", f"Product {product_identifier}")
                        product_image_url = product.get("whatsapp_image_url", product.get("image_url", ""))
            except:
                product_name = f"Product {product_identifier}"
        
        try:
            price_float = float(price)
        except ValueError:
            price_float = 0
            logger.warning(f"Could not parse price '{price}' for product {product_identifier}")
        
        # Check if product already in cart (check by both product_id and product_option_id)
        for item in current_cart:
            if (item["product_id"] == product_identifier or 
                (product_option_id and item.get("product_option_id") == product_option_id)):
                item["quantity"] += quantity
                session_ref.update({
                    'cart': current_cart,
                    'last_active': datetime.now()
                })
                logger.info(f"Updated quantity for product {product_identifier} in cart for user {user_id} in business {business_id}")
                return True
        
        # Add new item to cart
        cart_item = {
            "product_id": product_identifier,
            "product_option_id": product_option_id or "",  # Store resolved option ID
            "name": product_name,
            "price": price_float,
            "quantity": quantity,
            "image_url": product_image_url,
            "whatsapp_image_id": product_image_url,
            "currency": currency or "GHS",
            "business_id": business_id  # Ensure cart items are business-scoped
        }
        
        current_cart.append(cart_item)
        session_ref.update({
            'cart': current_cart,
            'last_active': datetime.now()
        })
        
        logger.info(f"Added product {product_identifier} to cart for user {user_id} in business {business_id} with price {price_float} {currency}")
        return True
        
    except Exception as e:
        logger.error(f"Error adding to cart with details for business {business_id}: {str(e)}")
        return False

def remove_from_cart(business_context, user_id, product_id):
    """Remove a product from the user's cart with business context"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db or not business_id:
        logger.error("Missing db or business_id in business context")
        return False
    
    try:
        session_ref = db.collection('whatsapp_sessions').document(f"{business_id}_{user_id}")
        session_doc = session_ref.get()
        
        if session_doc.exists:
            current_cart = session_doc.to_dict().get('cart', [])
            
            # Find and remove product
            for i, item in enumerate(current_cart):
                if item["product_id"] == product_id:
                    current_cart.pop(i)
                    session_ref.update({
                        'cart': current_cart,
                        'last_active': datetime.now()
                    })
                    logger.info(f"Removed product {product_id} from cart for user {user_id} in business {business_id}")
                    return True
        
        logger.warning(f"Failed to remove product {product_id} from cart - not found")
        return False
        
    except Exception as e:
        logger.error(f"Error removing from cart for business {business_id}: {str(e)}")
        return False

def update_cart_quantity(business_context, user_id, product_id, quantity):
    """Update the quantity of a product in the cart with business context"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db or not business_id:
        return False
    
    try:
        if quantity <= 0:
            return remove_from_cart(business_context, user_id, product_id)
        
        session_ref = db.collection('whatsapp_sessions').document(f"{business_id}_{user_id}")
        session_doc = session_ref.get()
        
        if session_doc.exists:
            current_cart = session_doc.to_dict().get('cart', [])
            
            # Find and update product quantity
            for item in current_cart:
                if item["product_id"] == product_id:
                    item["quantity"] = quantity
                    session_ref.update({
                        'cart': current_cart,
                        'last_active': datetime.now()
                    })
                    logger.info(f"Updated quantity for product {product_id} to {quantity} for user {user_id} in business {business_id}")
                    return True
        
        logger.warning(f"Failed to update quantity for product {product_id} - not found in cart")
        return False
        
    except Exception as e:
        logger.error(f"Error updating cart quantity for business {business_id}: {str(e)}")
        return False

def clear_cart(business_context, user_id):
    """Clear the user's shopping cart with business context"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db or not business_id:
        return False
    
    try:
        session_ref = db.collection('whatsapp_sessions').document(f"{business_id}_{user_id}")
        session_ref.update({
            'cart': [],
            'last_active': datetime.now()
        })
        logger.info(f"Cleared cart for user {user_id} in business {business_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error clearing cart for business {business_id}: {str(e)}")
        return False

def get_cart_total(business_context, user_id):
    """Calculate the total price of items in the cart with business context"""
    try:
        cart = get_cart(business_context, user_id)
        total = sum(item["price"] * item["quantity"] for item in cart)
        return total
    except Exception as e:
        logger.error(f"Error calculating cart total for business {business_context.get('business_id')}: {str(e)}")
        return 0

def get_cart_item_count(business_context, user_id):
    """Get the total number of items in the cart with business context"""
    try:
        cart = get_cart(business_context, user_id)
        return sum(item["quantity"] for item in cart)
    except Exception as e:
        logger.error(f"Error getting cart item count for business {business_context.get('business_id')}: {str(e)}")
        return 0

def format_cart_summary(business_context, user_id):
    """Format a text summary of the cart contents with business context"""
    try:
        cart = get_cart(business_context, user_id)
        
        if not cart:
            return "Your cart is empty."
        
        summary = "*Your Shopping Cart*\n\n"
        total = 0
        currency = cart[0].get("currency", "GHS")
        
        for item in cart:
            item_total = item["price"] * item["quantity"]
            summary += f"• {item['name']} x {item['quantity']} = {currency}{item_total:.2f}\n"
            total += item_total
        
        summary += f"\n*Total: {currency}{total:.2f}*"
        return summary
        
    except Exception as e:
        logger.error(f"Error formatting cart summary for business {business_context.get('business_id')}: {str(e)}")
        return "Error loading cart summary."

def update_cart_with_available_stock(business_context, user_id, modified_cart):
    """Update user's cart with only available stock quantities with business context"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db or not business_id:
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

def validate_cart_business_scope(business_context, user_id):
    """Validate that all cart items belong to the current business"""
    try:
        cart = get_cart(business_context, user_id)
        business_id = business_context.get('business_id')
        
        invalid_items = []
        for item in cart:
            # Check if item has business_id and if it matches current business
            item_business_id = item.get('business_id')
            if item_business_id and item_business_id != business_id:
                invalid_items.append(item)
        
        # Remove invalid items if any found
        if invalid_items:
            valid_cart = [item for item in cart if item.get('business_id') == business_id or not item.get('business_id')]
            
            # Update cart with only valid items
            db = business_context.get('db')
            if db:
                session_ref = db.collection('whatsapp_sessions').document(f"{business_id}_{user_id}")
                session_ref.update({
                    'cart': valid_cart,
                    'last_active': datetime.now()
                })
                
            logger.info(f"Removed {len(invalid_items)} invalid items from cart for user {user_id} in business {business_id}")
            return len(valid_cart)
        
        return len(cart)
        
    except Exception as e:
        logger.error(f"Error validating cart business scope: {str(e)}")
        return 0

def migrate_cart_to_business(business_context, user_id, old_cart_data):
    """Migrate cart data to business-scoped format"""
    try:
        business_id = business_context.get('business_id')
        
        # Add business_id to each cart item if not present
        updated_cart = []
        for item in old_cart_data:
            if 'business_id' not in item:
                item['business_id'] = business_id
            updated_cart.append(item)
        
        # Update the cart in Firebase
        db = business_context.get('db')
        if db:
            session_ref = db.collection('whatsapp_sessions').document(f"{business_id}_{user_id}")
            session_ref.update({
                'cart': updated_cart,
                'last_active': datetime.now()
            })
            
        logger.info(f"Migrated cart data for user {user_id} to business {business_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error migrating cart to business scope: {str(e)}")
        return False