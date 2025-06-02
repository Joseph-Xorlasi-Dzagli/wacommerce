from models.session import init_user_session
from services.catalog import get_product_by_id, get_product_by_retailer_id
from utils.logger import get_logger

logger = get_logger(__name__)

def get_cart(user_id):
    """Get the user's current shopping cart"""
    session = init_user_session(user_id)
    return session["cart"]

def add_to_cart(user_id, product_id, quantity=1):
    """Add a product to the user's cart"""
    session = init_user_session(user_id)
    
    # Get product details
    product = get_product_by_id(product_id)
    
    if not product:
        logger.error(f"Failed to add product {product_id} to cart - product not found")
        return False
    
    # Check if product already in cart
    for item in session["cart"]:
        if item["product_id"] == product_id:
            item["quantity"] += quantity
            logger.info(f"Updated quantity for product {product_id} in cart for user {user_id}")
            return True
    
    # Add new item to cart
    price = product.get("price", "0")
    if isinstance(price, str) and ' ' in price:
        # Handle price format like "10 USD"
        price = price.split()[0]
    
    try:
        price_float = float(price)
    except ValueError:
        price_float = 0
        logger.warning(f"Could not parse price '{price}' for product {product_id}")
    
    cart_item = {
        "product_id": product_id,
        "name": product["name"],
        "price": price_float,
        "quantity": quantity,
        "image_url": product.get("image_url", ""),
        "currency": product.get("currency", "USD")
    }
    
    session["cart"].append(cart_item)
    logger.info(f"Added product {product_id} to cart for user {user_id}")
    return True

def remove_from_cart(user_id, product_id):
    """Remove a product from the user's cart"""
    session = init_user_session(user_id)
    
    # Find and remove product
    for i, item in enumerate(session["cart"]):
        if item["product_id"] == product_id:
            session["cart"].pop(i)
            logger.info(f"Removed product {product_id} from cart for user {user_id}")
            return True
    
    logger.warning(f"Failed to remove product {product_id} from cart - not found")
    return False

def update_cart_quantity(user_id, product_id, quantity):
    """Update the quantity of a product in the cart"""
    session = init_user_session(user_id)
    
    if quantity <= 0:
        # If quantity is zero or negative, remove the item
        return remove_from_cart(user_id, product_id)
    
    # Find and update product quantity
    for item in session["cart"]:
        if item["product_id"] == product_id:
            item["quantity"] = quantity
            logger.info(f"Updated quantity for product {product_id} to {quantity} for user {user_id}")
            return True
    
    logger.warning(f"Failed to update quantity for product {product_id} - not found in cart")
    return False

def clear_cart(user_id):
    """Clear the user's shopping cart"""
    session = init_user_session(user_id)
    session["cart"] = []
    logger.info(f"Cleared cart for user {user_id}")
    return True

def get_cart_total(user_id):
    """Calculate the total price of items in the cart"""
    cart = get_cart(user_id)
    total = sum(item["price"] * item["quantity"] for item in cart)
    return total

def get_cart_item_count(user_id):
    """Get the total number of items in the cart"""
    cart = get_cart(user_id)
    return sum(item["quantity"] for item in cart)

def format_cart_summary(user_id):
    """Format a text summary of the cart contents"""
    cart = get_cart(user_id)
    
    if not cart:
        return "Your cart is empty."
    
    summary = "*Your Shopping Cart*\n\n"
    total = 0
    currency = cart[0].get("currency", "USD")
    
    for item in cart:
        item_total = item["price"] * item["quantity"]
        summary += f"• {item['name']} x {item['quantity']} = ${item_total:.2f}\n"
        total += item_total
    
    summary += f"\n*Total: ${total:.2f} {currency}*"
    return summary


def add_to_cart_with_details(user_id, product_id, quantity=1, price=None, currency=None):
    """Add a product to the user's cart with specific price details"""
    session = init_user_session(user_id)
    
    # If price is not provided, get product details
    product_name = ""
    product_image_url = ""
    
    if price is None:
        # Get product details from catalog
        product = get_product_by_retailer_id(product_id)
        
        if not product:
            logger.error(f"Failed to add product {product_id} to cart - product not found")
            return False
        
        # Get price from product
        price = product.get("price", "0")
        if isinstance(price, str) and ' ' in price:
            # Handle price format like "10 USD"
            price = price.split()[0]
        
        product_name = product.get("name", f"Product {product_id}")
        product_image_url = product.get("image_url", "")
        currency = product.get("currency", currency or "USD")
    else:
        # If we don't have product details but have the ID, try to get minimal info
        try:
            product = get_product_by_retailer_id(product_id)
            if product:
                product_name = product.get("name", f"Product {product_id}")
                product_image_url = product.get("image_url", "")
        except:
            product_name = f"Product {product_id}"
    
    try:
        price_float = float(price)
    except ValueError:
        price_float = 0
        logger.warning(f"Could not parse price '{price}' for product {product_id}")
    
    # Check if product already in cart
    for item in session["cart"]:
        if item["product_id"] == product_id:
            item["quantity"] += quantity
            logger.info(f"Updated quantity for product {product_id} in cart for user {user_id}")
            return True
    
    # Add new item to cart
    cart_item = {
        "product_id": product_id,
        "name": product_name,
        "price": price_float,
        "quantity": quantity,
        "image_url": product_image_url,
        "currency": currency or "USD"
    }
    
    session["cart"].append(cart_item)
    logger.info(f"Added product {product_id} to cart for user {user_id} with price {price_float} {currency}")
    return True