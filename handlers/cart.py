from models.cart import (
    get_cart, 
    add_to_cart, 
    remove_from_cart,
    update_cart_quantity,
    clear_cart,
    get_cart_total,
    get_cart_item_count,
    format_cart_summary
)
from models.session import init_user_session, set_current_action, get_current_action
from services.messenger import send_text_message, send_button_message, send_list_message
from services.catalog import get_product_by_id, get_product_by_retailer_id
from utils.logger import get_logger

logger = get_logger(__name__)

def handle_add_to_cart(user_id, product_id, quantity=1):
    """Handle adding a product to the cart"""
    logger.info(f"Handling add to cart for user {user_id}, product_id={product_id}, quantity={quantity}")
    
    if not product_id:
        send_text_message(user_id, "Please specify which product you'd like to add to your cart.")
        return False
    
    # Validate product
    product = get_product_by_id(product_id)
    if not product:
        send_text_message(user_id, "Sorry, I couldn't find that product.")
        return False
    
    # Add to cart
    success = add_to_cart(user_id, product_id, quantity)
    
    if not success:
        send_text_message(user_id, "Sorry, I couldn't add that product to your cart. Please try again.")
        return False
    
    # Send confirmation
    confirmation_message = f"Added {quantity} x {product['name']} to your cart."
    
    # Offer to view cart or continue shopping
    buttons = [
        {"type": "reply", "reply": {"id": "view_cart", "title": "View Cart"}},
        {"type": "reply", "reply": {"id": "browse", "title": "Continue Shopping"}}
    ]
    
    send_button_message(
        user_id,
        "Added to Cart",
        confirmation_message,
        buttons
    )
    
    return True

def handle_view_cart(user_id):
    """Handle viewing the cart contents"""
    logger.info(f"Handling view cart for user {user_id}")
    
    cart = get_cart(user_id)
    
    if not cart or len(cart) == 0:
        # Empty cart
        send_text_message(user_id, "Your cart is empty. Would you like to browse our products?")
        
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
        ]
        
        send_button_message(user_id, "Empty Cart", "Start shopping?", buttons)
        return True
    
    # Format cart summary
    cart_summary = format_cart_summary(user_id)
    
    # Send cart details with checkout button
    buttons = [
        {"type": "reply", "reply": {"id": "checkout", "title": "Checkout"}},
        {"type": "reply", "reply": {"id": "browse", "title": "Continue Shopping"}}
    ]
    
    send_button_message(
        user_id,
        "Your Cart",
        cart_summary,
        buttons
    )
    
    # Offer cart management options
    if len(cart) > 0:
        rows = []
        for item in cart:
            rows.append({
                "id": f"remove_{item['product_id']}",
                "title": f"Remove {item['name']}",
                "description": f"Quantity: {item['quantity']}"
            })
        
        # Add clear cart option
        rows.append({
            "id": "clear_cart",
            "title": "Clear Cart",
            "description": "Remove all items"
        })
        
        sections = [{
            "title": "Cart Management",
            "rows": rows
        }]
        
        send_list_message(
            user_id,
            "Manage Cart",
            "You can modify your cart here:",
            "Manage Cart",
            sections
        )
    
    return True

def handle_remove_from_cart(user_id, product_id):
    """Handle removing a product from the cart"""
    logger.info(f"Handling remove from cart for user {user_id}, product_id={product_id}")
    
    # Get product details for confirmation message
    product = get_product_by_id(product_id)
    product_name = product['name'] if product else "item"
    
    # Remove from cart
    success = remove_from_cart(user_id, product_id)
    
    if not success:
        send_text_message(user_id, "Sorry, I couldn't remove that item from your cart. Please try again.")
        return False
    
    # Send confirmation
    send_text_message(user_id, f"Removed {product_name} from your cart.")
    
    # Show updated cart
    return handle_view_cart(user_id)

def handle_clear_cart(user_id):
    """Handle clearing the entire cart"""
    logger.info(f"Handling clear cart for user {user_id}")
    
    # Clear cart
    clear_cart(user_id)
    
    # Send confirmation
    send_text_message(user_id, "Your cart has been cleared.")
    
    # Offer to browse products
    buttons = [
        {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
    ]
    
    send_button_message(
        user_id,
        "Cart Cleared",
        "Your cart is now empty. Would you like to continue shopping?",
        buttons
    )
    
    return True

def handle_update_cart_quantity(user_id, product_id, quantity):
    """Handle updating the quantity of a product in the cart"""
    logger.info(f"Handling update cart quantity for user {user_id}, product_id={product_id}, quantity={quantity}")
    
    # Update quantity
    success = update_cart_quantity(user_id, product_id, quantity)
    
    if not success:
        send_text_message(user_id, "Sorry, I couldn't update the quantity for that item. Please try again.")
        return False
    
    # Show updated cart
    return handle_view_cart(user_id)

def start_add_to_cart_flow(user_id):
    """Start the add to cart flow by asking for product"""
    send_text_message(user_id, "What product would you like to add to your cart?")
    set_current_action(user_id, "awaiting_product_for_cart")
    return True

def handle_awaiting_product_for_cart(user_id, message):
    """Handle response when waiting for product to add to cart"""
    from services.intent import analyze_message_content
    from handlers.browse import handle_browse_product
    
    # Analyze the message to find product
    intent = analyze_message_content(message)
    
    if intent["intent"] == "browse_product" and "entities" in intent and "product" in intent["entities"]:
        product_query = intent["entities"]["product"]
        # Search for product
        return handle_browse_product(user_id, product_query)
    else:
        # Just treat the whole message as a product query
        return handle_browse_product(user_id, message)
    

def add_to_cart_with_details(user_id, product_id, quantity=1, price=None, currency=None):
    """Add a product to the user's cart with specific price details"""
    session = init_user_session(user_id)
    
    # If price is not provided, get product details
    product_name = ""
    product_image_url = ""
    
    if price is None:
        # Get product details from catalog
        product = get_product_by_retailer_id(product_id)
        print(f"\n\nProduct details: {product}\n\n")

        
        if not product:
            logger.error(f"Failed to add product {product_id} to cart - product not found")
            return False
        
        # Get price from product
        price = product.get("price", "0")
        if isinstance(price, str) and ' ' in price:
            # Handle price format like "10 GHS"
            price = price.split()[0]
        
        product_name = product.get("name", f"Product {product_id}")
        product_image_url = product.get("image_url", "")
        currency = product.get("currency", currency or "GHS")
    else:
        # If we don't have product details but have the ID, try to get minimal info
        try:
            product = get_product_by_retailer_id(product_id)
            logger.debug(f"\n\nProduct details: {product}")
            print(f"\n\nProduct details: {product}")    
            if product:
                # The product response may have a "data" list with product info
                if "data" in product and isinstance(product["data"], list) and product["data"]:
                    product_name = product["data"][0].get("name", f"Product {product_id}")
                else:
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
        "currency": currency or "GHS"
    }
    print(f"\n\nCart item: {cart_item}\n\n")
    session["cart"].append(cart_item)
    logger.info(f"Added product {product_id} to cart for user {user_id} with price {price_float} {currency}")
    return True
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