from services.catalog import (
    fetch_product_details,
    get_all_categories, 
    get_products_by_category, 
    search_products_by_query,
    format_product_details,
    get_product_by_id,
    get_featured_products
)
from services.messenger import (
    send_text_message, 
    send_button_message, 
    send_list_message,
    send_product_card_carousel
)
from models.session import get_user_name, set_last_context, get_last_context, set_current_action
from utils.logger import get_logger
from config import CATALOG_ID

logger = get_logger(__name__)

def handle_browse_catalog(user_id, category=None, offset=0):
    """Handle browse catalog intent"""
    logger.info(f"Handling browse catalog for user {user_id}, category={category}, offset={offset}")
    
    if not category:
        # Show categories first
        categories = get_all_categories()
        
        if not categories:
            # If categories couldn't be fetched, refresh product details
            fetch_product_details()
            categories = get_all_categories()
            
            if not categories:
                send_text_message(user_id, "Sorry, I couldn't fetch our product categories at the moment. Please try again later.")
                return
        
        # If we have too many categories, use a list message
        if len(categories) > 3:
            rows = []
            for category in categories:
                rows.append({
                    "id": f"cat_{category}",
                    "title": category.title(),
                    "description": f"Browse all {category.lower()} products"
                })
                
            sections = [{
                "title": "Product Categories",
                "rows": rows
            }]
            
            send_list_message(
                user_id,
                "Product Categories",
                "Browse our product categories:",
                "View Categories",
                sections
            )
        else:
            # For few categories, use buttons
            buttons = []
            for category in categories:
                buttons.append({
                    "type": "reply", 
                    "reply": {
                        "id": f"cat_{category}", 
                        "title": category.title()
                    }
                })
            
            send_button_message(
                user_id,
                "Product Categories",
                "Choose a category to browse our products:",
                buttons
            )
    else:
        # Show products in the selected category
        products = get_products_by_category(category, offset=offset, limit=10)
        
        if not products:
            send_text_message(user_id, f"Sorry, no products found in the {category} category.")
            
            # Offer to browse all categories
            handle_browse_catalog(user_id)
            return
        
        # Get total products in this category for pagination info
        total_products = len(get_products_by_category(category, offset=0, limit=1000))
        
        # Set last context for pagination
        set_last_context(user_id, {
            "action": "browse_category",
            "category": category,
            "offset": offset,
            "total_products": total_products
        })
        
        # For each product, add a "See more like this" button
        # This is handled by modifying how we send the product cards
        send_product_carousel_with_more_button(
            user_id,
            products,
            f"{category.title()} Products",
            get_user_name(user_id),
            category
        )
        
        # Show page navigation
        if total_products > 10:
            # Calculate next offset, handling wraparound
            next_offset = (offset + 10) % total_products
            
            # Show current page information
            page_info = f"Showing products {offset+1}-{min(offset+10, total_products)} of {total_products} in {category.title()}"
            
            send_text_message(user_id, page_info)
            
            # Navigation buttons
            buttons = [
                {"type": "reply", "reply": {"id": f"more_{category}_{next_offset}", "title": "See More Products"}},
                {"type": "reply", "reply": {"id": "browse", "title": "Browse Categories"}}
            ]
            
            send_button_message(
                user_id,
                "Navigation",
                "What would you like to do next?",
                buttons
            )

def send_product_carousel_with_more_button(user_id, products, header_text, recipient_name, category):
    """Send a product carousel with a 'See more like this' option"""
    # Get the total products and current offset from context
    context = get_last_context(user_id)
    total_products = context.get("total_products", 0) if context else 0
    current_offset = context.get("offset", 0) if context else 0
    
    # Prepare a message that will be sent before the carousel
    # explaining how to see more products
    if total_products > 10:
        browsing_instructions = (
            f"*{header_text}*\n\n"
            f"To see more products in this category, select any product and then click 'See more like this'."
        )
        send_text_message(user_id, browsing_instructions)
    
    # Now send the actual product carousel
    try:
        # Enhance products with catalog_id and add see_more button info
        for product in products:
            if "catalog_id" not in product:
                product["catalog_id"] = CATALOG_ID
            if "retailer_id" not in product and "id" in product:
                product["retailer_id"] = product["id"]
            
            # We'll add a context identifier to the product
            # so we can track "see more like this" clicks
            product["see_more_context"] = f"more_{category}_{current_offset}"
        
        # Send product carousel
        from services.messenger import send_product_card_carousel
        send_product_card_carousel(
            user_id,
            products,
            header_text,
            recipient_name
        )
        
        return True
    except Exception as e:
        logger.error(f"Error sending product carousel: {str(e)}")
        
        # Fallback to text list if carousel fails
        products_text = f"*{header_text}:*\n\n"
        for i, product in enumerate(products, 1):
            price = product.get("price", "N/A")
            products_text += f"{i}. {product['name']} - ${price}\n"
        
        send_text_message(user_id, products_text)
        
        # Offer product selection buttons
        buttons = []
        for i, product in enumerate(products[:3], 1):
            buttons.append({
                "type": "reply", 
                "reply": {
                    "id": f"product_{product['id']}", 
                    "title": f"View {product['name'][:20]}"
                }
            })
        
        send_button_message(
            user_id,
            "Product Selection",
            "Select a product to view details:",
            buttons
        )
        
        return False

def handle_product_details(user_id, product_id):
    """Handle showing details for a specific product"""
    logger.info(f"Handling product details for user {user_id}, product_id={product_id}")
    
    # Get product details
    product = get_product_by_id(product_id)
    
    if not product:
        send_text_message(user_id, "Sorry, I couldn't find details for this product.")
        return False
    
    # Format product details
    product_details = format_product_details(product)
    
    # Check if we have category context for this product
    context = get_last_context(user_id)
    category = context.get("category", None) if context else None
    
    # Send details with add to cart and see more like this buttons
    buttons = [
        {"type": "reply", "reply": {"id": f"add_{product_id}", "title": "Add to Cart"}}
    ]
    
    # Add "See more like this" button if we have category context
    if category:
        # Get current offset and total products
        current_offset = context.get("offset", 0)
        total_products = context.get("total_products", 0)
        
        # Calculate next set of products (wrap around if at the end)
        next_offset = (current_offset + 10) % total_products if total_products > 0 else 0
        
        buttons.append({
            "type": "reply", 
            "reply": {
                "id": f"more_{category}_{next_offset}", 
                "title": "See more like this"
            }
        })
    
    # Add browse more button
    buttons.append({
        "type": "reply", 
        "reply": {
            "id": "browse", 
            "title": "Browse Categories"
        }
    })
    
    send_button_message(
        user_id,
        product.get("name", "Product Details"),
        product_details,
        buttons[:3]  # WhatsApp has a limit of 3 buttons
    )
    
    return True

def handle_see_more_like_this(user_id, category, offset):
    """Handle see more like this request for products"""
    logger.info(f"Handling see more like this for user {user_id}, category={category}, offset={offset}")
    
    # Convert offset to int if it's a string
    if isinstance(offset, str):
        try:
            offset = int(offset)
        except ValueError:
            offset = 0
    
    # Browse the category with the specified offset
    return handle_browse_catalog(user_id, category, offset)

def handle_browse_product(user_id, product_query):
    """Handle browse specific product intent"""
    logger.info(f"Handling product search for user {user_id}, query={product_query}")
    
    if not product_query:
        send_text_message(user_id, "What product are you looking for?")
        set_current_action(user_id, "awaiting_product_query")
        return True
    
    # Search for products matching the query
    products = search_products_by_query(product_query)
    
    if not products or len(products) == 0:
        send_text_message(
            user_id, 
            f"Sorry, I couldn't find any products matching '{product_query}'. Would you like to browse our categories instead?"
        )
        
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Categories"}},
            {"type": "reply", "reply": {"id": "search_again", "title": "Search Again"}}
        ]
        
        send_button_message(
            user_id,
            "No Products Found",
            "What would you like to do?",
            buttons
        )
        return True
    
    # Set context for pagination
    set_last_context(user_id, {
        "action": "search_results",
        "query": product_query,
        "offset": 0
    })
    
    # Try to send product carousel
    try:
        send_product_card_carousel(
            user_id,
            products,
            f"Search Results: {product_query}",
            get_user_name(user_id)
        )
        
        # Show options buttons
        if len(products) > 1:
            buttons = [
                {"type": "reply", "reply": {"id": "browse", "title": "Browse Categories"}},
                {"type": "reply", "reply": {"id": "search_again", "title": "Search Again"}}
            ]
            
            send_button_message(
                user_id,
                "Search Results",
                f"Found {len(products)} products matching '{product_query}'.",
                buttons
            )
    except Exception as e:
        logger.error(f"Error sending search results carousel: {str(e)}")
        
        # Fallback to text list if carousel fails
        results_text = f"*Search Results for '{product_query}':*\n\n"
        for i, product in enumerate(products[:5], 1):
            price = product.get("price", "N/A")
            results_text += f"{i}. {product['name']} - ${price}\n"
        
        send_text_message(user_id, results_text)
        
        # Offer product selection buttons
        buttons = []
        for i, product in enumerate(products[:3], 1):
            buttons.append({
                "type": "reply", 
                "reply": {
                    "id": f"product_{product['id']}", 
                    "title": f"View {product['name'][:20]}"
                }
            })
        
        send_button_message(
            user_id,
            "Product Selection",
            "Select a product to view details:",
            buttons
        )
    
    return True

def handle_featured_products(user_id):
    """Handle showing featured products"""
    logger.info(f"Handling featured products for user {user_id}")
    
    products = get_featured_products(limit=10)
    
    if not products or len(products) == 0:
        send_text_message(user_id, "Sorry, we couldn't find any featured products at the moment.")
        return False
    
    try:
        send_product_card_carousel(
            user_id,
            products,
            "Featured Products",
            get_user_name(user_id)
        )
        
        # Show options buttons
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Categories"}},
            {"type": "reply", "reply": {"id": "view_cart", "title": "View Cart"}}
        ]
        
        send_button_message(
            user_id,
            "Our Top Picks",
            "Check out these featured products handpicked for you!",
            buttons
        )
        
        return True
    except Exception as e:
        logger.error(f"Error sending featured products carousel: {str(e)}")
        
        # Fallback to text list
        featured_text = "*Featured Products:*\n\n"
        for i, product in enumerate(products[:5], 1):
            price = product.get("price", "N/A")
            featured_text += f"{i}. {product['name']} - ${price}\n"
        
        send_text_message(user_id, featured_text)
        return False