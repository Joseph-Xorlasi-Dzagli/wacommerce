from models.cart import (
    get_cart, 
    add_to_cart, 
    remove_from_cart,
    clear_cart,
    format_cart_summary
)
from models.session import set_current_action
from services.messenger import send_text_message, send_button_message, send_list_message
from services.catalog import get_product_by_id
from utils.logger import get_logger

logger = get_logger(__name__)

def handle_add_to_cart(business_context, user_id, product_id, quantity=1):
    """Handle adding a product to the cart with business context"""
    logger.info(f"Handling add to cart for user {user_id}, product_id={product_id}, quantity={quantity}, business={business_context.get('business_id')}")
    
    if not product_id:
        send_text_message(business_context, user_id, "Please specify which product you'd like to add to your cart.")
        return False
    
    # Validate product belongs to this business
    product = get_product_by_id(business_context, product_id)
    if not product:
        send_text_message(business_context, user_id, "Sorry, I couldn't find that product.")
        return False
    
    # Verify product belongs to the current business
    if product.get('business_id') != business_context.get('business_id'):
        send_text_message(business_context, user_id, "Sorry, that product is not available.")
        return False
    
    # Add to cart with business context
    success = add_to_cart(business_context, user_id, product_id, quantity)
    
    if not success:
        send_text_message(business_context, user_id, "Sorry, I couldn't add that product to your cart. Please try again.")
        return False
    
    # Send confirmation
    confirmation_message = f"Added {quantity} x {product['name']} to your cart."
    
    # Offer to view cart or continue shopping
    buttons = [
        {"type": "reply", "reply": {"id": "view_cart", "title": "View Cart"}},
        {"type": "reply", "reply": {"id": "browse", "title": "Continue Shopping"}}
    ]
    
    send_button_message(
        business_context,
        user_id,
        "Added to Cart",
        confirmation_message,
        buttons
    )
    
    return True

def handle_view_cart(business_context, user_id):
    """Handle viewing the cart contents with business context"""
    logger.info(f"Handling view cart for user {user_id}, business={business_context.get('business_id')}")
    
    cart = get_cart(business_context, user_id)
    
    if not cart or len(cart) == 0:
        # Empty cart
        send_text_message(business_context, user_id, "Your cart is empty. Would you like to browse our products?")
        
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
        ]
        
        send_button_message(business_context, user_id, "Empty Cart", "Start shopping?", buttons)
        return True
    
    # Format cart summary
    cart_summary = format_cart_summary(business_context, user_id)
    
    # Send cart details with checkout button
    buttons = [
        {"type": "reply", "reply": {"id": "checkout", "title": "Checkout"}},
        {"type": "reply", "reply": {"id": "browse", "title": "Continue Shopping"}}
    ]
    
    send_button_message(
        business_context,
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
            business_context,
            user_id,
            "Manage Cart",
            "You can modify your cart here:",
            "Manage Cart",
            sections
        )
    
    return True

def handle_remove_from_cart(business_context, user_id, product_id):
    """Handle removing a product from the cart with business context"""
    logger.info(f"Handling remove from cart for user {user_id}, product_id={product_id}, business={business_context.get('business_id')}")
    
    # Get product details for confirmation message
    product = get_product_by_id(business_context, product_id)
    product_name = product['name'] if product else "item"
    
    # Remove from cart
    success = remove_from_cart(business_context, user_id, product_id)
    
    if not success:
        send_text_message(business_context, user_id, "Sorry, I couldn't remove that item from your cart. Please try again.")
        return False
    
    # Send confirmation
    send_text_message(business_context, user_id, f"Removed {product_name} from your cart.")
    
    # Show updated cart
    return handle_view_cart(business_context, user_id)

def handle_clear_cart(business_context, user_id):
    """Handle clearing the entire cart with business context"""
    logger.info(f"Handling clear cart for user {user_id}, business={business_context.get('business_id')}")
    
    # Clear cart
    clear_cart(business_context, user_id)
    
    # Send confirmation
    send_text_message(business_context, user_id, "Your cart has been cleared.")
    
    # Offer to browse products
    buttons = [
        {"type": "reply", "reply": {"id": "browse", "title": "Browse Products"}}
    ]
    
    send_button_message(
        business_context,
        user_id,
        "Cart Cleared",
        "Your cart is now empty. Would you like to continue shopping?",
        buttons
    )
    
    return True

def handle_awaiting_product_for_cart(business_context, user_id, message):
    """Handle response when waiting for product to add to cart with business context"""
    from services.intent import analyze_message_content
    from handlers.browse import handle_browse_product
    
    # Analyze the message to find product
    intent = analyze_message_content(message)
    
    if intent["intent"] == "browse_product" and "entities" in intent and "product" in intent["entities"]:
        product_query = intent["entities"]["product"]
        # Search for product
        return handle_browse_product(business_context, user_id, product_query)
    else:
        # Just treat the whole message as a product query
        return handle_browse_product(business_context, user_id, message)