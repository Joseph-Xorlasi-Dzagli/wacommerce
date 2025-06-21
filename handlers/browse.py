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
import time

logger = get_logger(__name__)

def handle_browse_catalog(business_context, user_id, category=None, offset=0):
    """Handle browse catalog intent with business context"""
    logger.info(f"Handling browse catalog for user {user_id}, category={category}, offset={offset}, business={business_context.get('business_id')}")
    
    if not category:
        # Show categories first
        categories = get_all_categories(business_context)
        categories = sorted(categories, key=lambda x: x["name"].lower())
        
        if not categories:
            # If categories couldn't be fetched, refresh product details
            fetch_product_details(business_context)
            categories = get_all_categories(business_context)
            
            if not categories:
                send_text_message(business_context, user_id, "Sorry, I couldn't fetch our product categories at the moment. Please try again later.")
                return
        
        # If we have too many categories (more than 9), organize them into sections
        if len(categories) > 9:
            # Distribute categories across sections
            section_size = len(categories) // 3
            sections = []
            
            for i in range(0, len(categories), section_size):
                section_categories = categories[i:i + section_size]
                rows = []
                
                for category in section_categories:
                    rows.append({
                        "id": f"cat_{category['id']}",
                        "title": category["name"],
                        "description": category.get("description", f"Browse all {category['name'].lower()} products")
                    })
                
                if rows:
                    first_letter = section_categories[0]["name"][0].upper()
                    last_letter = section_categories[-1]["name"][0].upper()
                    sections.append({
                        "title": f"Categories {first_letter} - {last_letter}",
                        "rows": rows
                    })
            
            send_list_message(
                business_context,
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
                    "id": f"cat_{category['id']}",
                    "title": category["name"],
                    "description": category.get("description", f"Browse all {category['name'].lower()} products")
                })
                
            sections = [{
                "title": "Product Categories",
                "rows": rows
            }]
            
            send_list_message(
                business_context,
                user_id,
                "Product Categories",
                "Browse our product categories:",
                "View Categories",
                sections
            )
    else:
        # Show products in the selected category using media card carousel
        products = get_products_by_category(business_context, category, offset=offset, limit=10)
        
        if not products:
            send_text_message(business_context, user_id, f"Sorry, no products found in this category.")
            handle_browse_catalog(business_context, user_id)
            return
        
        # Get category name - handle both string and dict cases
        category_name = category
        if isinstance(category, dict):
            category_name = category.get("name", category.get("id", "Unknown"))
        else:
            # Get category name from ID
            categories = get_all_categories(business_context)
            category_name = category  # Default fallback
            for cat in categories:
                if cat["id"] == category:
                    category_name = cat["name"]
                    break
        
        # Get total products in this category for pagination info
        total_products = len(get_products_by_category(business_context, category, offset=0, limit=1000))
        
        # Set last context for pagination
        set_last_context(user_id, {
            "action": "browse_category",
            "category": category,
            "offset": offset,
            "total_products": total_products,
            "business_id": business_context.get('business_id')
        })
        
        # Send media card carousel for category browsing
        send_category_media_carousel(business_context, user_id, products, category_name)
        
        # Show page navigation if there are more products
        if total_products > 10:
            # Calculate next offset, handling wraparound
            next_offset = (offset + 10) % total_products
            
            # Show current page information
            page_info = f"Showing products {offset+1}-{min(offset+10, total_products)} of {total_products} in {category_name}"
            
            send_text_message(business_context, user_id, page_info)
            
            # Navigation buttons
            buttons = [
                {"type": "reply", "reply": {"id": f"more_{category}_{next_offset}", "title": "See More Products"}},
                {"type": "reply", "reply": {"id": "browse", "title": "Browse Categories"}}
            ]
            
            send_button_message(
                business_context,
                user_id,
                "Navigation",
                "What would you like to do next?",
                buttons
            )

def send_category_media_carousel(business_context, user_id, products, category):
    """Send a media card carousel for category browsing"""
    try:
        # Prepare cards for media carousel
        cards = []
        for product in products[:10]:  # Limit to 10 as per WhatsApp restrictions
            card = {
                "image_id": "1220367125959487",
                "product_name": product['name'],
                "price": product['price'],
                "quick_reply_payload": f"view_options_{product['id']}"
            }
            cards.append(card)
        
        # Send media card carousel
        customer_name = get_user_name(user_id)
        
        send_media_card_carousel(
            business_context,
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
            products_text += f"{i}. {product['name']} - GHS {price}\n"
        
        send_text_message(business_context, user_id, products_text)
        
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
            business_context,
            user_id,
            "Select Product",
            "Choose a product to view options:",
            buttons
        )
        
        return False

def handle_view_product_options(business_context, user_id, product_id):
    """Handle viewing product options/variants"""
    logger.info(f"Handling view product options for user {user_id}, product_id={product_id}, business={business_context.get('business_id')}")
    
    # Get base product details
    base_product = get_product_by_id(business_context, product_id)
    
    if not base_product:
        send_text_message(business_context, user_id, "Sorry, I couldn't find details for this product.")
        return False
    
    # Check if product has options/variants from database
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    product_options = []
    
    if db and business_id:
        try:
            # Get product options from Firebase
            from firebase_admin import firestore
            options_ref = db.collection('product_options').where(
                filter=firestore.FieldFilter('product_id', '==', product_id)
            ).limit(10)
            
            options_docs = options_ref.get()
            for option_doc in options_docs:
                option_data = option_doc.to_dict()
                option_data['id'] = option_doc.id
                product_options.append(option_data)
                
        except Exception as e:
            logger.error(f"Error fetching product options: {str(e)}")
    
    if not product_options:
        send_single_product_message(business_context, user_id, base_product)
        return True
    
    try:
        # Send product card carousel for variants
        send_product_card_carousel(
            business_context,
            user_id,
            product_options,
            base_product['name']
        )

        # Ensure the product carousel completes before calling browse catalog
        time.sleep(2)

        handle_browse_catalog(business_context, user_id)
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending product options carousel: {str(e)}")
        
        # Fallback to list format
        options_text = f"*Available Options for {base_product['name']}:*\n\n"
        for i, variant in enumerate(product_options[:5], 1):
            price = variant.get("price", "N/A")
            variant_details = []
            attributes = variant.get("attributes", {})
            if attributes.get("size"):
                variant_details.append(f"Size: {attributes['size']}")
            if attributes.get("color"):
                variant_details.append(f"Color: {attributes['color']}")
            
            details_str = " | ".join(variant_details) if variant_details else "Standard"
            options_text += f"{i}. {variant['name']} ({details_str}) - GHS{price}\n"
        
        send_text_message(business_context, user_id, options_text)
        
        # Offer selection buttons
        buttons = []
        for i, variant in enumerate(product_options[:3], 1):
            buttons.append({
                "type": "reply",
                "reply": {
                    "id": f"product_{variant['id']}",
                    "title": f"Option {i}"
                }
            })
        
        send_button_message(
            business_context,
            user_id,
            "Select Option",
            "Choose an option to view details:",
            buttons
        )
        
        return True

def handle_product_details(business_context, user_id, product_id):
    """Handle showing details for a specific product"""
    logger.info(f"Handling product details for user {user_id}, product_id={product_id}, business={business_context.get('business_id')}")
    
    # Get product details
    product = get_product_by_id(business_context, product_id)
    
    if not product:
        send_text_message(business_context, user_id, "Sorry, I couldn't find details for this product.")
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
        business_context,
        user_id,
        product.get("name", "Product Details"),
        product_details,
        buttons[:3]  # WhatsApp has a limit of 3 buttons
    )
    
    return True

def handle_see_more_like_this(business_context, user_id, category, offset):
    """Handle see more like this request for products"""
    logger.info(f"Handling see more like this for user {user_id}, category={category}, offset={offset}, business={business_context.get('business_id')}")
    
    # Convert offset to int if it's a string
    if isinstance(offset, str):
        try:
            offset = int(offset)
        except ValueError:
            offset = 0
    
    # Browse the category with the specified offset
    return handle_browse_catalog(business_context, user_id, category, offset)

def handle_browse_product(business_context, user_id, product_query):
    """Handle browse specific product intent"""
    logger.info(f"Handling product search for user {user_id}, query={product_query}, business={business_context.get('business_id')}")
    
    if not product_query:
        send_text_message(business_context, user_id, "What product are you looking for?")
        set_current_action(user_id, "awaiting_product_query")
        return True
    
    # Search for products matching the query
    products = search_products_by_query(business_context, product_query)
    
    if not products or len(products) == 0:
        send_text_message(
            business_context,
            user_id, 
            f"Sorry, I couldn't find any products matching '{product_query}'. Would you like to browse our categories instead?"
        )
        
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Categories"}},
            {"type": "reply", "reply": {"id": "search_again", "title": "Search Again"}}
        ]
        
        send_button_message(
            business_context,
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
        "offset": 0,
        "business_id": business_context.get('business_id')
    })
    
    # For search results, use media card carousel too
    send_search_media_carousel(business_context, user_id, products, product_query)
    
    return True

def send_search_media_carousel(business_context, user_id, products, query):
    """Send media card carousel for search results"""
    try:
        # Prepare cards for media carousel
        cards = []
        for product in products[:10]:
            card = {
                "image_id": product.get("whatsapp_image_id", "1220367125959487"),
                "product_name": product.get("name", "Product"),
                "price": product.get("price", "0"),
                "quick_reply_payload": f"view_options_{product['id']}"
            }
            cards.append(card)
        
        send_text_message(
            business_context,
            user_id,
            f"*Search Results for '{query}'*\n\n"
            f"Found {len(products)} products. Click 'View Options' to see details."
        )
        
        # Send media card carousel
        customer_name = get_user_name(user_id)
        send_media_card_carousel(
            business_context,
            user_id,
            customer_name,
            f"Search: {query}",
            cards
        )
        
        # Show navigation options
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Categories"}},
            {"type": "reply", "reply": {"id": "search_again", "title": "Search Again"}}
        ]
        
        send_button_message(
            business_context,
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
            results_text += f"{i}. {product['name']} - GHS{price}\n"
        
        send_text_message(business_context, user_id, results_text)
        
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
            business_context,
            user_id,
            "Product Selection",
            "Select a product to view options:",
            buttons
        )
        
        return False

def handle_featured_products(business_context, user_id):
    """Handle showing featured products"""
    logger.info(f"Handling featured products for user {user_id}, business={business_context.get('business_id')}")
    
    products = get_featured_products(business_context, limit=10)
    
    if not products or len(products) == 0:
        send_text_message(business_context, user_id, "Sorry, we couldn't find any featured products at the moment.")
        return False
    
    # Use media card carousel for featured products
    try:
        cards = []
        for product in products[:10]:
            card = {
                "image_id": product.get("whatsapp_image_id", "1220367125959487"),
                "product_name": product.get("name", "Product"),
                "price": product.get("price", "0"),
                "quick_reply_payload": f"view_options_{product['id']}"
            }
            cards.append(card)
        
        send_text_message(
            business_context,
            user_id,
            "*Featured Products*\n\n"
            "Check out these handpicked products!"
        )
        
        customer_name = get_user_name(user_id)
        send_media_card_carousel(
            business_context,
            user_id,
            customer_name,
            "Featured",
            cards
        )
        
        # Show options buttons
        buttons = [
            {"type": "reply", "reply": {"id": "browse", "title": "Browse Categories"}},
            {"type": "reply", "reply": {"id": "view_cart", "title": "View Cart"}}
        ]
        
        send_button_message(
            business_context,
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
            featured_text += f"{i}. {product['name']} - GHS{price}\n"
        
        send_text_message(business_context, user_id, featured_text)
        return False