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
    send_single_product_message,
    send_text_message, 
    send_button_message, 
    send_list_message,
    send_product_card_carousel,
    send_media_card_carousel
)
from models.session import get_user_name, set_last_context, get_last_context, set_current_action
from utils.logger import get_logger
from config import CATALOG_ID, product_options_cache
import time

logger = get_logger(__name__)

def handle_browse_catalog(user_id, category=None, offset=0):
    """Handle browse catalog intent"""
    logger.info(f"Handling browse catalog for user {user_id}, category={category}, offset={offset}")
    
    if not category:
        # Show categories first
        categories = get_all_categories()
        categories = sorted(categories, key=lambda x: x.lower())
        
        if not categories:
            # If categories couldn't be fetched, refresh product details
            fetch_product_details()
            categories = get_all_categories()
            
            if not categories:
                send_text_message(user_id, "Sorry, I couldn't fetch our product categories at the moment. Please try again later.")
                return
        
        # If we have too many categories (more than 9), organize them into three sections
        if len(categories) > 9:
            # Distribute categories across three sections
            top_picks = categories[:len(categories)//3]
            trending_now = categories[len(categories)//3:2*len(categories)//3]
            explore_more = categories[2*len(categories)//3:]
            
            # Create sections for the list message
            sections = []
            
            # Add Top Picks section
            top_rows = []
            for cat in top_picks:
                top_rows.append({
                    "id": f"cat_{cat}",
                    "title": cat.title(),
                    "description": f"Browse {cat.lower()} products"
                })
            
            if top_rows:
                first_letter = top_picks[0][0].upper()
                last_letter = top_picks[-1][0].upper()
                sections.append({
                    "title": f"Categories {first_letter} - {last_letter}",
                    "rows": top_rows
                })
            
            # Add Trending Now section
            trending_rows = []
            for cat in trending_now:
                trending_rows.append({
                    "id": f"cat_{cat}",
                    "title": cat.title(),
                    "description": f"Browse {cat.lower()} products"
                })
            
            if trending_rows:
                first_letter = trending_now[0][0].upper()
                last_letter = trending_now[-1][0].upper()
                sections.append({
                    "title": f"Categories {first_letter} - {last_letter}",
                    "rows": trending_rows
                })
            
            # Add Explore More section
            explore_rows = []
            for cat in explore_more:
                explore_rows.append({
                    "id": f"cat_{cat}",
                    "title": cat.title(),
                    "description": f"Browse {cat.lower()} products"
                })
            
            if explore_rows:
                first_letter = explore_more[0][0].upper()
                last_letter = explore_more[-1][0].upper()
                sections.append({
                    "title": f"Categories {first_letter} - {last_letter}",
                    "rows": explore_rows
                })
            
            send_list_message(
                user_id,
                "Product Categories",
                "Browse our product categories:",
                "View Categories",
                sections
            )

        else:
            # For fewer categories, use the original list approach
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
        # Show products in the selected category using media card carousel
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
        
        # Send media card carousel for category browsing
        send_category_media_carousel(user_id, products, category)
        
        # Show page navigation if there are more products
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

def send_category_media_carousel(user_id, products, category):
    """Send a media card carousel for category browsing"""
    try:
        # Prepare cards for media carousel
        cards = []
        for product in products[:10]:  # Limit to 10 as per WhatsApp restrictions
            # Prepare card data
            # card = {
            #     "image_id": "1220367125959487",  # Use default if no image
            #     "quick_reply_payload": f"view_options_{product['id']}",
            #     "quick_reply_text": "View Options",
            #     "url_button_text": product.get("name", "Product")[:20]  # Limit text length
            # }
            card = {
            "image_id": "1220367125959487",
            "product_name": product['name'],
            "price": product['price'],
            "quick_reply_payload": f"view_options_{product['id']}"
            }
            cards.append(card)
        
       
        
        # Send media card carousel
        # Using generic template parameters for demo
        customer_name = get_user_name(user_id)
        discount_percent = "10%"  # Can be dynamic based on user/category
        promo_code = "SAVE10"    # Can be dynamic

        send_media_card_carousel(
            user_id,
            customer_name,
            category,
            cards
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending media card carousel: {str(e)}")
        
        # Fallback to text list
        products_text = f"*{category.title()} Products:*\n\n"
        for i, product in enumerate(products[:10], 1):
            price = product.get("price", "N/A")
            products_text += f"{i}. {product['name']} - ${price}\n"
        
        send_text_message(user_id, products_text)
        
        # Offer product selection buttons
        buttons = []
        for i, product in enumerate(products[:3], 1):
            buttons.append({
                "type": "reply", 
                "reply": {
                    "id": f"view_options_{product['id']}", 
                    "title": f"{product['name'][:15]}..."
                }
            })
        
        send_button_message(
            user_id,
            "Select Product",
            "Choose a product to view options:",
            buttons
        )
        
        return False

def handle_view_product_options(user_id, product_id):
    """Handle viewing product options/variants"""
    logger.info(f"Handling view product options for user {user_id}, product_id={product_id}")
    
    # Get base product details
    base_product = get_product_by_id(product_id)
    
    if not base_product:
        send_text_message(user_id, "Sorry, I couldn't find details for this product.")
        return False
    
    # Check if product has options/variants
    product_options = product_options_cache.get(product_id, [])

    
    if not product_options:
        send_single_product_message(user_id, base_product)
        return True
    
    # Get details for all product variants
    variant_products = []
    for variant_id in product_options[:10]:  # Limit to 10 for carousel
        variant = get_product_by_id(variant_id)
        if variant:
            variant_products.append(variant)
    
    if not variant_products:
        send_single_product_message(user_id, base_product)
        return True

    
    print(f"Variant products: {variant_products}")
    
    try:
        # Send product card carousel for variants
        send_product_card_carousel(
            user_id,
            variant_products,
            base_product['name']
        )

        # Ensure the product carousel completes before calling browse catalog
        time.sleep(5)  # Wait 1 second to allow the carousel to send before browsing catalog

        handle_browse_catalog(user_id)
        
        # Add navigation buttons
        context = get_last_context(user_id)
        category = context.get("category") if context else None
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending product options carousel: {str(e)}")
        
        # Fallback to list format
        options_text = f"*Available Options for {base_product['name']}:*\n\n"
        for i, variant in enumerate(variant_products[:5], 1):
            price = variant.get("price", "N/A")
            variant_details = []
            if variant.get("size"):
                variant_details.append(f"Size: {variant['size']}")
            if variant.get("color"):
                variant_details.append(f"Color: {variant['color']}")
            
            details_str = " | ".join(variant_details) if variant_details else "Standard"
            options_text += f"{i}. {variant['name']} ({details_str}) - ${price}\n"
        
        send_text_message(user_id, options_text)
        
        # Offer selection buttons
        buttons = []
        for i, variant in enumerate(variant_products[:3], 1):
            buttons.append({
                "type": "reply",
                "reply": {
                    "id": f"product_{variant['id']}",
                    "title": f"Option {i}"
                }
            })
        
        send_button_message(
            user_id,
            "Select Option",
            "Choose an option to view details:",
            buttons
        )
        
        return True

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
    
    # Send details with add to cart and navigation buttons
    buttons = [
        {"type": "reply", "reply": {"id": f"add_{product_id}", "title": "Add to Cart"}}
    ]
    
    # Add navigation options
    if category:
        buttons.append({
            "type": "reply", 
            "reply": {
                "id": f"cat_{category}", 
                "title": "Back to Category"
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
    
    # For search results, use media card carousel too
    send_search_media_carousel(user_id, products, product_query)
    
    return True

def send_search_media_carousel(user_id, products, query):
    """Send media card carousel for search results"""
    try:
        # Prepare cards for media carousel
        cards = []
        for product in products[:10]:
            card = {
                "image_id": product.get("image_url", "2362891770745441"),
                "quick_reply_payload": f"view_options_{product['id']}",
                "quick_reply_text": "View Options",
                "url_button_text": product.get("name", "Product")[:20]
            }
            cards.append(card)
        
        send_text_message(
            user_id,
            f"*Search Results for '{query}'*\n\n"
            f"Found {len(products)} products. Click 'View Options' to see details."
        )
        
        # Send media card carousel
        customer_name = get_user_name(user_id)
        send_media_card_carousel(
            user_id,
            customer_name,
            "10%",
            "SEARCH10",
            cards
        )
        
        # Show navigation options
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Categories"}},
            {"type": "reply", "reply": {"id": "search_again", "title": "Search Again"}}
        ]
        
        send_button_message(
            user_id,
            "Search Complete",
            "What would you like to do next?",
            buttons
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending search results carousel: {str(e)}")
        
        # Fallback to text list
        results_text = f"*Search Results for '{query}':*\n\n"
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
                    "id": f"view_options_{product['id']}", 
                    "title": f"View {product['name'][:15]}"
                }
            })
        
        send_button_message(
            user_id,
            "Product Selection",
            "Select a product to view options:",
            buttons
        )
        
        return False

def handle_featured_products(user_id):
    """Handle showing featured products"""
    logger.info(f"Handling featured products for user {user_id}")
    
    products = get_featured_products(limit=10)
    
    if not products or len(products) == 0:
        send_text_message(user_id, "Sorry, we couldn't find any featured products at the moment.")
        return False
    
    # Use media card carousel for featured products
    try:
        cards = []
        for product in products[:10]:
            card = {
                "image_id": product.get("image_url", "2362891770745441"),
                "quick_reply_payload": f"view_options_{product['id']}",
                "quick_reply_text": "View Options",
                "url_button_text": product.get("name", "Product")[:20]
            }
            cards.append(card)
        
        send_text_message(
            user_id,
            "*Featured Products*\n\n"
            "Check out these handpicked products!"
        )
        
        customer_name = get_user_name(user_id)
        send_media_card_carousel(
            user_id,
            customer_name,
            "15%",
            "FEATURED15",
            cards
        )
        
        # Show options buttons
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Categories"}},
            {"type": "reply", "reply": {"id": "view_cart", "title": "View Cart"}}
        ]
        
        send_button_message(
            user_id,
            "More Options",
            "What would you like to do next?",
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

# Keep the original send_product_carousel_with_more_button for backwards compatibility
# but it's not used in the new media card flow
def send_product_carousel_with_more_button(user_id, products, header_text, recipient_name, category):
    """Legacy function - kept for compatibility"""
    return send_product_card_carousel(user_id, products, header_text, recipient_name)