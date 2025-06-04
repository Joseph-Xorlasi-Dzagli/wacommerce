from handlers.greeting import handle_greeting
from models.session import get_last_context
from handlers.browse import (
    handle_browse_catalog, 
    handle_browse_product,
    handle_product_details,
    handle_featured_products,
    handle_see_more_like_this,
    handle_view_product_options  # New handler for product options
)
from handlers.cart import (
    handle_add_to_cart,
    handle_remove_from_cart,
    handle_clear_cart,
    handle_update_cart_quantity,
    start_add_to_cart_flow,
    handle_awaiting_product_for_cart
)
from handlers.checkout import (
    handle_checkout,
    handle_confirm_checkout,
    handle_payment_selection,
    handle_shipping_options,
    handle_shipping_selection,
    handle_shipping_address,
    handle_momo_network_selection,
    handle_momo_number_submission,
    handle_existing_momo_payment,
    handle_new_momo_request,
    handle_shipping_location,
    handle_delivery_instructions,
    handle_save_address_decision,
    handle_existing_address_selection,
    # NEW: Add inventory-related handlers
    handle_proceed_with_available,
    handle_cancel_inventory_order
)
from handlers.order import (
    handle_order_status,
    handle_show_orders,
    handle_track_order,
    handle_cancel_order,
    handle_confirm_cancel_order
)
from handlers.support import (
    handle_support,
    handle_support_faq,
    handle_support_shipping,
    handle_support_returns,
    handle_support_contact,
    handle_connect_agent,
    handle_feedback,
    handle_feedback_response,
    handle_rating_submission,
    handle_cancel
)

# Map of intent types to handler functions
intent_handlers = {
    "greeting": handle_greeting,
    "browse_catalog": handle_browse_catalog,
    "browse_product": handle_browse_product,
    "product_info": handle_product_details,
    "add_to_cart": handle_add_to_cart,
    # Removed "view_cart" intent
    "checkout": handle_checkout,
    "order_status": handle_order_status,
    "support": handle_support,
    "feedback": handle_feedback,
    "cancel": handle_cancel
}

# Map of button/interaction IDs to handler functions
interaction_handlers = {
    # Browse and catalog
    "browse": handle_browse_catalog,
    "featured": handle_featured_products,
    "search_again": lambda user_id: start_add_to_cart_flow(user_id),
    
    # Removed cart view interactions
    "clear_cart": handle_clear_cart,
    
    # Checkout flow
    "checkout": handle_checkout,
    "confirm_checkout": handle_confirm_checkout,
    
    # NEW: Inventory decision handlers
    "proceed_with_available": handle_proceed_with_available,
    "cancel_inventory_order": handle_cancel_inventory_order,
    
    # Mobile Money payment options
    "payment_new_momo": lambda user_id: handle_new_momo_request(user_id, get_last_context(user_id).get("order_id", "")),
    "payment_cod": lambda user_id: handle_payment_selection(user_id, "payment_cod"),
    
    # Shipping options
    "shipping_new_address": lambda user_id: handle_shipping_selection(user_id, "shipping_new_address"),
    "shipping_location": lambda user_id: handle_shipping_selection(user_id, "shipping_location"),
    "shipping_pickup": lambda user_id: handle_shipping_selection(user_id, "shipping_pickup"),

    # Support options
    "support": handle_support,
    "support_faq": handle_support_faq,
    "support_shipping": handle_support_shipping,
    "support_returns": handle_support_returns,
    "support_contact": handle_support_contact,
    "connect_agent": handle_connect_agent
}

def get_handler_for_intent(intent):
    """Get the appropriate handler function for an intent"""
    return intent_handlers.get(intent)

def get_handler_for_interaction(interaction_id):
    """Get the appropriate handler function for an interaction ID"""
    # First check exact matches
    if interaction_id in interaction_handlers:
        return interaction_handlers[interaction_id]
    
    # Check for pattern matches
    if interaction_id.startswith("cat_"):
        category = interaction_id[4:]
        return lambda user_id: handle_browse_catalog(user_id, category)
    
    elif interaction_id.startswith("view_options_"):
        # New handler for viewing product options
        product_id = interaction_id[13:]
        return lambda user_id: handle_view_product_options(user_id, product_id)
    
    elif interaction_id.startswith("product_"):
        product_id = interaction_id[8:]
        return lambda user_id: handle_product_details(user_id, product_id)
    
    elif interaction_id.startswith("add_"):
        product_id = interaction_id[4:]
        return lambda user_id: handle_add_to_cart(user_id, product_id)
    
    elif interaction_id.startswith("remove_"):
        product_id = interaction_id[7:]
        return lambda user_id: handle_remove_from_cart(user_id, product_id)
    
    elif interaction_id.startswith("update_qty_"):
        parts = interaction_id[11:].split("_")
        if len(parts) == 2:
            product_id, quantity = parts
            return lambda user_id: handle_update_cart_quantity(user_id, product_id, int(quantity))
    
    elif interaction_id.startswith("more_"):
        parts = interaction_id[5:].split("_")
        if len(parts) == 2:
            category, offset = parts
            return lambda user_id: handle_see_more_like_this(user_id, category, int(offset))
    
    elif interaction_id.startswith("payment_momo_"):
        account_id = interaction_id[13:]
        return lambda user_id: handle_existing_momo_payment(
            user_id, 
            get_last_context(user_id).get("order_id", ""),
            account_id
        )
    
    elif interaction_id.startswith("momo_network_"):
        network = interaction_id[13:]
        return lambda user_id: handle_momo_network_selection(user_id, network)
    
    elif interaction_id.startswith("shipping_address_"):
        address_id = interaction_id[17:]
        # Create a closure that gets the order_id from context when called
        return lambda user_id: (
            handle_existing_address_selection(
                user_id, 
                get_last_context(user_id).get("order_id", ""),  # Get order_id from context
                address_id
            )
        )
    
    elif interaction_id.startswith("save_address_"):
        order_id = interaction_id[13:]
        return lambda user_id: handle_save_address_decision(user_id, "save", order_id)
    
    elif interaction_id.startswith("no_save_address_"):
        order_id = interaction_id[16:]
        return lambda user_id: handle_save_address_decision(user_id, "no_save", order_id)
    
    elif interaction_id.startswith("order_"):
        order_id = interaction_id[6:]
        return lambda user_id: handle_order_status(user_id, order_id)
    
    elif interaction_id.startswith("track_"):
        order_id = interaction_id[6:]
        return lambda user_id: handle_track_order(user_id, order_id)
    
    elif interaction_id.startswith("cancel_"):
        order_id = interaction_id[7:]
        return lambda user_id: handle_cancel_order(user_id, order_id)
    
    elif interaction_id.startswith("confirm_cancel_"):
        order_id = interaction_id[15:]
        return lambda user_id: handle_confirm_cancel_order(user_id, order_id)
    
    elif interaction_id.startswith("rating_"):
        rating = int(interaction_id[7:])
        return lambda user_id: handle_rating_submission(user_id, rating)
    
    # No handler found
    return None