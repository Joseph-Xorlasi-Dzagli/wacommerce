import requests
from config import WHATSAPP_TOKEN, BUSINESS_ACCOUNT_ID, CATALOG_ID, product_cache, category_cache
from utils.logger import get_logger

logger = get_logger(__name__)

def fetch_catalog():
    """Fetch the business catalog and product list from WhatsApp Business API"""
    url = f"https://graph.facebook.com/v22.0/{BUSINESS_ACCOUNT_ID}/product_catalogs"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch catalog: {response.text}")
            return None, None
        
        catalogs = response.json().get("data", [])
        if not catalogs:
            logger.warning("No catalogs found for this business account")
            return None, None
        
        # Get the first catalog ID
        catalog_id = catalogs[0]["id"]
        
        # Now fetch the products in this catalog
        url = f"https://graph.facebook.com/v22.0/{catalog_id}/products"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch products: {response.text}")
            return None, None
        
        products = response.json().get("data", [])
        logger.info(f"Fetched {len(products)} products from catalog {catalog_id}")
        
        return products, catalog_id
    
    except Exception as e:
        logger.error(f"Error fetching catalog: {str(e)}")
        return None, None

def fetch_product_details(catalog_id=None):
    """Fetch comprehensive details of all products in a catalog"""
    if not catalog_id:
        catalog_id = CATALOG_ID
    
    # If we still don't have a catalog ID, try to fetch catalogs first
    if not catalog_id:
        products, catalog_id = fetch_catalog()
        if not catalog_id:
            logger.error("No catalog ID available")
            return None
    
    # Fetch all products in the catalog with detailed information
    url = f"https://graph.facebook.com/v22.0/{catalog_id}/products"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    params = {
        "fields": "id,name,description,url,image_url,brand,availability,condition,price,sale_price,category,retailer_id,inventory,color,size,currency,visibility"
    }
    
    try:
        all_products = []
        next_page = True
        
        while next_page:
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch products: {response.text}")
                break
            
            product_data = response.json()
            products = product_data.get("data", [])
            all_products.extend(products)
            
            # Check if there are more pages
            paging = product_data.get("paging", {})
            if "next" in paging:
                url = paging["next"]
            else:
                next_page = False
        
        # Log the number of products fetched
        logger.info(f"Fetched {len(all_products)} products from catalog {catalog_id}")
        
        # Update global product cache
        for product in all_products:
            product_cache[product["id"]] = product
            
            # Add catalog_id to the product
            product["catalog_id"] = catalog_id
            
            # Organize products by category for easier access
            if "category" in product:
                category = product["category"]
                if category not in category_cache:
                    category_cache[category] = []
                category_cache[category].append(product["id"])
        
        return all_products
    
    except Exception as e:
        logger.error(f"Error fetching product details: {str(e)}")
        return None

def get_product_by_id(product_id, catalog_id=None):
    """Fetch detailed information for a specific product"""
    # Check cache first
    if product_id in product_cache:
        logger.debug(f"Product {product_id} found in cache")
        print(f"Product {product_cache[product_id]} found in this cache hereche")
        return product_cache[product_id]
    
    if not catalog_id:
        catalog_id = CATALOG_ID
    
    # If not in cache, fetch from API
    try:
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        url = f"https://graph.facebook.com/v22.0/{product_id}"
        params = {
            "fields": "id,name,description,url,image_url,brand,availability,condition,price,sale_price,additional_image_urls,category,retailer_id,variants,inventory,color,size,currency,visibility"
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch product {product_id}: {response.text}")
            return None
        
        product = response.json()
        
        # Add catalog_id to the product
        product["catalog_id"] = catalog_id
        
        # Update cache
        product_cache[product_id] = product
        
        # Update category cache
        if "category" in product:
            category = product["category"]
            if category not in category_cache:
                category_cache[category] = []
            if product_id not in category_cache[category]:
                category_cache[category].append(product_id)
        
        return product
    
    except Exception as e:
        logger.error(f"Error fetching product by ID: {str(e)}")
        return None

def search_products_by_query(query, limit=10):
    """Search products based on a text query"""
    # If product cache is empty, fetch all products first
    if not product_cache:
        fetch_product_details()
    
    # Simple search implementation
    query = query.lower()
    results = []
    
    try:
        for product_id, product in product_cache.items():
            # Search in name, description, and category
            name = product.get("name", "").lower()
            description = product.get("description", "").lower()
            category = product.get("category", "").lower()
            
            if (query in name) or (query in description) or (query in category):
                results.append(product)
                
                if len(results) >= limit:
                    break
        
        return results
    except Exception as e:
        logger.error(f"Error searching products: {str(e)}")
        return []

def get_products_by_category(category, offset=0, limit=10):
    """Get products from a specific category"""
    # If category cache is empty, fetch all products first
    if not category_cache:
        fetch_product_details()
    
    try:
        if category not in category_cache:
            logger.warning(f"Category '{category}' not found in cache")
            return []
        
        product_ids = category_cache[category][offset:offset+limit]
        products = []
        
        for pid in product_ids:
            if pid in product_cache:
                products.append(product_cache[pid])
            else:
                # If product not in cache, try to fetch it
                product = get_product_by_id(pid)
                if product:
                    products.append(product)
        
        return products
    except Exception as e:
        logger.error(f"Error getting products by category: {str(e)}")
        return []

def get_all_categories():
    """Get all unique product categories"""
    # If category cache is empty, fetch all products first
    if not category_cache:
        fetch_product_details()
    
    return list(category_cache.keys())

def get_featured_products(limit=5):
    """Get a list of featured products"""
    # If product cache is empty, fetch all products first
    if not product_cache:
        fetch_product_details()
    
    # For now, simply return some random products
    # In a real implementation, this would use a "featured" flag or other criteria
    import random
    
    products = list(product_cache.values())
    if len(products) <= limit:
        return products
    
    return random.sample(products, limit)

def format_product_details(product):
    """Format product details as a text message"""
    if not product:
        return "Product details not available."
    
    details = f"*{product['name']}*\n\n"
    
    if "description" in product and product["description"]:
        details += f"{product['description']}\n\n"
    
    if "price" in product:
        price = product["price"]
        currency = product.get("currency", "GHS")
        if isinstance(price, str) and ' ' in price:
            # Handle price format like "10 GHS"
            details += f"*Price:* {price}\n"
        else:
            details += f"*Price:* {price} {currency}\n"
    
    if "sale_price" in product and product["sale_price"]:
        details += f"*Sale Price:* {product['sale_price']}\n"
    
    if "brand" in product and product["brand"]:
        details += f"*Brand:* {product['brand']}\n"
    
    if "availability" in product and product["availability"]:
        details += f"*Availability:* {product['availability']}\n"
    
    if "color" in product and product["color"]:
        details += f"*Color:* {product['color']}\n"
    
    if "size" in product and product["size"]:
        details += f"*Size:* {product['size']}\n"
    
    return details

def initialize_catalog():
    """Initialize the product catalog on startup"""
    logger.info("Initializing product catalog...")
    fetch_product_details()
    logger.info(f"Catalog initialized with {len(product_cache)} products and {len(category_cache)} categories")

def get_product_by_retailer_id(retailer_id, catalog_id=None):
    """Fetch product details using the retailer_id from the catalog"""
    print(f"Fetching product by retailer_id: {retailer_id}")
    if not catalog_id:
        catalog_id = CATALOG_ID

    if not catalog_id:
        _, catalog_id = fetch_catalog()
        if not catalog_id:
            logger.error("No catalog ID available")
            return None

    # Fixed URL construction - proper JSON encoding for filter parameter
    import json
    filter_param = json.dumps({'retailer_id': {'contains': retailer_id}})
    url = f"https://graph.facebook.com/v22.0/{catalog_id}/products"
    
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    params = {
        "fields": "id,name,description,url,image_url,brand,availability,condition,price,sale_price,additional_image_urls,category,retailer_id,variants,inventory,color,size,currency,visibility",
        "filter": filter_param
    }

    try:
        print(f"Fetching product by retailer_id: {retailer_id} with catalog_id: {catalog_id}")
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            logger.error(f"Failed to fetch product by retailer_id {retailer_id}: {response.text}")
            return None

        data = response.json()
        print(f"API Response: {data}")
        
        # Handle the response structure - Facebook Graph API returns data in 'data' array
        if 'data' not in data or not data['data']:
            logger.warning(f"No products found for retailer_id: {retailer_id}")
            return None
        
        # Get the first product from the results
        product = data['data'][0]
        product["catalog_id"] = catalog_id
        
        # Use product ID if available, otherwise use retailer_id as fallback
        product_key = product.get("id", retailer_id)
        product_cache[product_key] = product

        # Handle category caching
        if "category" in product:
            category = product["category"]
            if category not in category_cache:
                category_cache[category] = []
            if product_key not in category_cache[category]:
                category_cache[category].append(product_key)

        logger.info(f"Fetched product {product_key} by retailer_id {retailer_id}") 
        return product
        
    except Exception as e:
        logger.error(f"Error fetching product by retailer_id: {str(e)}")
        return None
