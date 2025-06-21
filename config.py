import os
from dotenv import load_dotenv
import logging
import firebase_admin
from firebase_admin import credentials, firestore

# Load environment variables
load_dotenv()

# Global credentials (fallback only)
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Firebase configuration
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")

# Initialize Firebase
try:
    if not firebase_admin._apps:
        if os.path.exists(FIREBASE_CREDENTIALS_PATH):
            cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred, {
                'projectId': FIREBASE_PROJECT_ID,
            })
        else:
            # Use default credentials (for production deployment)
            firebase_admin.initialize_app()
    
    # Initialize Firestore
    db = firestore.client()
    
except Exception as e:
    print(f"Firebase initialization error: {e}")
    db = None

# OpenAI settings
OPENAI_MODEL = "gpt-3.5-turbo"

# Flask configuration
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")
PORT = int(os.getenv("PORT", "5000"))

# Inventory management settings
INVENTORY_CACHE_DURATION_MINUTES = 30
INVENTORY_CHECK_ENABLED = True
DEFAULT_STOCK_QUANTITY = 7

# Business context caching
BUSINESS_CONFIG_CACHE_DURATION_MINUTES = 15
BUSINESS_CONFIG_CACHE = {}
BUSINESS_CONFIG_CACHE_UPDATED = {}

# In-memory caches for performance (now business-scoped)
# Format: {business_id: {cache_data}}
business_product_cache = {}
business_category_cache = {}
business_product_options_cache = {}
business_inventory_cache = {}
business_inventory_cache_updated = {}

# Session storage (now business-scoped)
# Format: {business_id: {user_sessions}}
business_sessions = {}

# Order storage (now business-scoped)
# Format: {business_id: [orders]}
business_orders = {}

# Mobile money networks (could be business-specific in future)
MOBILE_MONEY_NETWORKS = ["MTN", "Vodafone", "AirtelTigo"]

# Default fallback configurations
DEFAULT_WHATSAPP_CONFIG = {
    "greeting_message": "👋 Welcome to our WhatsApp store! How can I help you today?",
    "business_hours_message": "We're currently closed. Our business hours are Mon-Sat: 9AM-6PM.",
    "auto_reply_enabled": True,
    "inventory_check_enabled": True,
    "low_stock_threshold": 5
}

DEFAULT_CHECKOUT_CONFIG = {
    "payment_methods": ["mobile_money", "cash_on_delivery"],
    "shipping_methods": ["delivery", "pickup"],
    "tax_rate": 0.0,
    "currency": "GHS",
    "require_phone_verification": False
}

# Error messages
ERROR_MESSAGES = {
    "business_not_found": "Business configuration not found. Please contact support.",
    "business_inactive": "This business is currently inactive.",
    "whatsapp_not_enabled": "WhatsApp integration is not enabled for this business.",
    "configuration_error": "Configuration error. Please try again later.",
    "database_error": "Database connection error. Please try again later."
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('whatsapp_store')

# Helper functions for business-scoped caches
def get_business_cache(business_id, cache_type):
    """Get business-specific cache"""
    cache_map = {
        'products': business_product_cache,
        'categories': business_category_cache,
        'product_options': business_product_options_cache,
        'inventory': business_inventory_cache
    }
    
    cache = cache_map.get(cache_type, {})
    if business_id not in cache:
        cache[business_id] = {}
    return cache[business_id]

def get_business_sessions(business_id):
    """Get business-specific sessions"""
    if business_id not in business_sessions:
        business_sessions[business_id] = {}
    return business_sessions[business_id]

def get_business_orders(business_id):
    """Get business-specific orders"""
    if business_id not in business_orders:
        business_orders[business_id] = []
    return business_orders[business_id]