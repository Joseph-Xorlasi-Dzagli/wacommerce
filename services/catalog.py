import requests
import json
from datetime import datetime
from utils.logger import get_logger
from firebase_admin import firestore

logger = get_logger(__name__)

def fetch_catalog(business_context):
    """Fetch the business catalog and product list from WhatsApp Business API"""
    business_account_id = business_context.get('business_account_id')
    whatsapp_token = business_context.get('whatsapp_token')
    
    if not business_account_id or not whatsapp_token:
        logger.error("Missing business account ID or WhatsApp token")
        return None, None
    
    url = f"https://graph.facebook.com/v22.0/{business_account_id}/product_catalogs"
    
    headers = {
        "Authorization": f"Bearer {whatsapp_token}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch catalog for business {business_context.get('business_id')}: {response.text}")
            return None, None
        
        catalogs = response.json().get("data", [])
        if not catalogs:
            logger.warning(f"No catalogs found for business account {business_account_id}")
            return None, None
        
        # Get the first catalog ID
        catalog_id = catalogs[0]["id"]
        
        # Fetch products in this catalog
        url = f"https://graph.facebook.com/v22.0/{catalog_id}/products"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch products: {response.text}")
            return None, None
        
        products = response.json().get("data", [])
        logger.info(f"Fetched {len(products)} products from catalog {catalog_id} for business {business_context.get('business_id')}")
        
        return products, catalog_id
    
    except Exception as e:
        logger.error(f"Error fetching catalog for business {business_context.get('business_id')}: {str(e)}")
        return None, None

def fetch_product_details(business_context, catalog_id=None):
    """Fetch comprehensive details of all products in a catalog"""
    if not catalog_id:
        catalog_id = business_context.get('catalog_id')
    
    if not catalog_id:
        products, catalog_id = fetch_catalog(business_context)
        if not catalog_id:
            logger.error(f"No catalog ID available for business {business_context.get('business_id')}")
            return None
    
    whatsapp_token = business_context.get('whatsapp_token')
    business_id = business_context.get('business_id')
    
    url = f"https://graph.facebook.com/v22.0/{catalog_id}/products"
    headers = {"Authorization": f"Bearer {whatsapp_token}"}
    params = {
        "fields": "id,name,description,url,image_url,brand,availability,condition,price,sale_price,category,retailer_id,inventory,color,size,currency,visibility"
    }
    
    try:
        all_products = []
        next_page = True
        
        while next_page:
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch products for business {business_id}: {response.text}")
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
        
        logger.info(f"Fetched {len(all_products)} products from catalog {catalog_id} for business {business_id}")
        
        # Sync with Firebase
        sync_products_to_firebase(all_products, catalog_id, business_context)
        
        return all_products
    
    except Exception as e:
        logger.error(f"Error fetching product details for business {business_id}: {str(e)}")
        return None

def sync_products_to_firebase(products, catalog_id, business_context):
    """Sync products to Firebase database with business context"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db or not business_id:
        logger.warning("Firebase or business ID not available, skipping sync")
        return
    
    try:
        for product in products:
            product_data = {
                "business_id": business_id,
                "whatsapp_product_id": product["id"],
                "retailer_id": product.get("retailer_id", product["id"]),
                "name": product.get("name", ""),
                "description": product.get("description", ""),
                "whatsapp_image_url": product.get("image_url", ""),
                "whatsapp_image_id": product.get("image_url", ""),
                "price": product.get("price", "0"),
                "currency": product.get("currency", "GHS"),
                "category_id": product.get("category", "uncategorized"),
                "brand": product.get("brand", ""),
                "availability": product.get("availability", "in_stock"),
                "condition": product.get("condition", "new"),
                "track_inventory": True,
                "stock_quantity": 999,  # Default stock
                "is_featured": False,
                "sync_status": "synced",
                "last_synced": datetime.now(),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            # Use retailer_id as document ID for consistency
            product_ref = db.collection('products').document(product.get("retailer_id", product["id"]))
            product_ref.set(product_data, merge=True)
        
        logger.info(f"Synced {len(products)} products to Firebase for business {business_id}")
        
    except Exception as e:
        logger.error(f"Error syncing products to Firebase for business {business_id}: {str(e)}")

def get_product_by_id(business_context, product_id, catalog_id=None):
    """Fetch detailed information for a specific product"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    # Check Firebase first
    if db and business_id:
        try:
            product_ref = db.collection('products').document(product_id)
            product_doc = product_ref.get()
            if product_doc.exists:
                product_data = product_doc.to_dict()
                # Verify this product belongs to the current business
                if product_data.get('business_id') == business_id:
                    return product_data
        except Exception as e:
            logger.error(f"Error fetching product from Firebase: {str(e)}")
    
    if not catalog_id:
        catalog_id = business_context.get('catalog_id')
    
    # Fetch from WhatsApp API
    try:
        whatsapp_token = business_context.get('whatsapp_token')
        headers = {"Authorization": f"Bearer {whatsapp_token}"}
        url = f"https://graph.facebook.com/v22.0/{product_id}"
        params = {
            "fields": "id,name,description,url,image_url,brand,availability,condition,price,sale_price,additional_image_urls,category,retailer_id,variants,inventory,color,size,currency,visibility"
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch product {product_id} for business {business_id}: {response.text}")
            return None
        
        product = response.json()
        product["catalog_id"] = catalog_id
        product["business_id"] = business_id
        
        return product
    
    except Exception as e:
        logger.error(f"Error fetching product by ID for business {business_id}: {str(e)}")
        return None

def get_product_by_retailer_id(business_context, retailer_id, catalog_id=None):
    """Fetch product details using the retailer_id from the catalog"""
    logger.debug(f"Fetching product by retailer_id: {retailer_id} for business {business_context.get('business_id')}")
    
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    # Check Firebase first
    if db and business_id:
        try:
            product_ref = db.collection('products').document(retailer_id)
            product_doc = product_ref.get()
            if product_doc.exists:
                product_data = product_doc.to_dict()
                # Verify this product belongs to the current business
                if product_data.get('business_id') == business_id:
                    return product_data
        except Exception as e:
            logger.error(f"Error fetching product from Firebase: {str(e)}")
    
    if not catalog_id:
        catalog_id = business_context.get('catalog_id')

    if not catalog_id:
        _, catalog_id = fetch_catalog(business_context)
        if not catalog_id:
            logger.error(f"No catalog ID available for business {business_id}")
            return None

    # Search in WhatsApp API
    whatsapp_token = business_context.get('whatsapp_token')
    filter_param = json.dumps({'retailer_id': {'contains': retailer_id}})
    url = f"https://graph.facebook.com/v22.0/{catalog_id}/products"
    
    headers = {"Authorization": f"Bearer {whatsapp_token}"}
    params = {
        "fields": "id,name,description,url,image_url,brand,availability,condition,price,sale_price,additional_image_urls,category,retailer_id,variants,inventory,color,size,currency,visibility",
        "filter": filter_param
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            logger.error(f"Failed to fetch product by retailer_id {retailer_id} for business {business_id}: {response.text}")
            return None

        data = response.json()
        
        if 'data' not in data or not data['data']:
            logger.warning(f"No products found for retailer_id: {retailer_id} in business {business_id}")
            return None
        
        product = data['data'][0]
        product["catalog_id"] = catalog_id
        product["business_id"] = business_id

        logger.info(f"Fetched product {product.get('id')} by retailer_id {retailer_id} for business {business_id}") 
        return product
        
    except Exception as e:
        logger.error(f"Error fetching product by retailer_id for business {business_id}: {str(e)}")
        return None

def search_products_by_query(business_context, query, limit=10):
    """Search products based on a text query"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    # Check Firebase first
    if db and business_id:
        try:
            products_ref = db.collection('products').where('business_id', '==', business_id)
            products = products_ref.get()
            
            results = []
            query_lower = query.lower()
            
            for product_doc in products:
                product_data = product_doc.to_dict()
                product_data["id"] = product_doc.id
                
                name = product_data.get("name", "").lower()
                description = product_data.get("description", "").lower()
                category = product_data.get("category_id", "").lower()
                
                if (query_lower in name) or (query_lower in description) or (query_lower in category):
                    results.append(product_data)
                    
                    if len(results) >= limit:
                        break
            
            if results:
                return results
                
        except Exception as e:
            logger.error(f"Error searching products in Firebase for business {business_id}: {str(e)}")
    
    return []

def get_products_by_category(business_context, category, offset=0, limit=10):
    """Get products from a specific category"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    # Check Firebase first
    if db and business_id:
        try:
            products_ref = db.collection('products').where(
                filter=firestore.FieldFilter('business_id', '==', business_id)
            ).where(
                filter=firestore.FieldFilter('category_id', '==', category)
            ).offset(offset).limit(limit)
            
            products = products_ref.get()
            
            results = []
            for product_doc in products:
                product_data = product_doc.to_dict()
                product_data["id"] = product_doc.id
                results.append(product_data)
            
            return results
                
        except Exception as e:
            logger.error(f"Error getting products by category from Firebase for business {business_id}: {str(e)}")
    
    return []

def get_all_categories(business_context):
    """Get all unique product categories with names"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    # Check Firebase first
    if db and business_id:
        try:
            categories_ref = db.collection('categories').where('business_id', '==', business_id)
            categories = categories_ref.get()
            
            category_list = []
            for cat_doc in categories:
                cat_data = cat_doc.to_dict()
                category_list.append({
                    "id": cat_doc.id,
                    "name": cat_data.get("name", cat_doc.id),
                    "description": cat_data.get("description", "")
                })
            
            return category_list
                
        except Exception as e:
            logger.error(f"Error getting categories from Firebase for business {business_id}: {str(e)}")
    
    return []

def get_featured_products(business_context, limit=5):
    """Get a list of featured products"""
    db = business_context.get('db')
    business_id = business_context.get('business_id')
    
    # Check Firebase first
    if db and business_id:
        try:
            products_ref = db.collection('products').where('business_id', '==', business_id).where('is_featured', '==', True).limit(limit)
            products = products_ref.get()
            
            results = []
            for product_doc in products:
                product_data = product_doc.to_dict()
                product_data["id"] = product_doc.id
                results.append(product_data)
            
            if results:
                return results
                
        except Exception as e:
            logger.error(f"Error getting featured products from Firebase for business {business_id}: {str(e)}")
    
    # Fallback to random selection from all products
    try:
        import random
        all_products = search_products_by_query(business_context, "", limit=50)  # Get more for random selection
        if len(all_products) <= limit:
            return all_products
        
        return random.sample(all_products, limit)
    except Exception as e:
        logger.error(f"Error getting fallback featured products for business {business_id}: {str(e)}")
        return []

def format_product_details(product):
    """Format product details as a text message"""
    if not product:
        return "Product details not available."
    
    details = f"*{product.get('name', 'Unknown Product')}*\n\n"
    
    if "description" in product and product["description"]:
        details += f"{product['description']}\n\n"
    
    if "price" in product:
        price = product["price"]
        currency = product.get("currency", "GHS")
        if isinstance(price, str) and ' ' in price:
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

def initialize_catalog(business_context):
    """Initialize the product catalog on startup for a specific business"""
    business_id = business_context.get('business_id')
    logger.info(f"Initializing product catalog for business {business_id}...")
    
    products = fetch_product_details(business_context)
    if products:
        logger.info(f"Catalog initialized with {len(products)} products for business {business_id}")
    else:
        logger.warning(f"Failed to initialize catalog for business {business_id}")