import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# API credentials
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
BUSINESS_ACCOUNT_ID = os.getenv("BUSINESS_ACCOUNT_ID")
CATALOG_ID = os.getenv("CATALOG_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# WhatsApp API endpoints
WHATSAPP_API_URL = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"

# OpenAI settings
OPENAI_MODEL = "gpt-3.5-turbo"

# Flask configuration
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")
PORT = int(os.getenv("PORT", "5000"))

# In-memory storage (will be replaced with proper database in production) , "29934692319448320", "29721762554073939", "29767553459502718", "9533864750054764"
# These are initialized here to be shared across modules 1220367125959487:
sessions = {}
orders = []
product_cache = {}


# Inventory management settings
INVENTORY_CACHE_DURATION_MINUTES = 30
INVENTORY_CHECK_ENABLED = True
DEFAULT_STOCK_QUANTITY = 7  # Default when inventory data is unavailable

# Add inventory cache to the in-memory storage section
inventory_cache = {}
inventory_cache_updated = None

# Update the existing sessions dictionary to support inventory decisions
# Add this to the session initialization in models/session.py:
# "inventory_results": None,  # Store inventory check results
# "awaiting_inventory_decision": False,  # Track if waiting for inventory decision

# Sample inventory data for testing (can be removed in production)
MOCK_INVENTORY_DATA = {
    "29731645503115608": {"stock_quantity": 15, "stock_status": "in_stock"},
    "9754687801263091": {"stock_quantity": 3, "stock_status": "low_stock"}, 
    "9715602025185036": {"stock_quantity": 0, "stock_status": "out_of_stock"},
    "9536779646410457": {"stock_quantity": 8, "stock_status": "in_stock"},
    "9610090482419920": {"stock_quantity": 1, "stock_status": "low_stock"},
    "29392834080360744": {"stock_quantity": 22, "stock_status": "in_stock"},
    "29180309118279910": {"stock_quantity": 0, "stock_status": "out_of_stock"},
    "9560808797375497": {"stock_quantity": 12, "stock_status": "in_stock"},
    "29239261912387560": {"stock_quantity": 2, "stock_status": "low_stock"},
    "29368899942725277": {"stock_quantity": 18, "stock_status": "in_stock"},
    "30331860066413533": {"stock_quantity": 5, "stock_status": "low_stock"},
    "9130680133704059": {"stock_quantity": 0, "stock_status": "out_of_stock"},
    "23939808892293564": {"stock_quantity": 25, "stock_status": "in_stock"},
    "9674011849346532": {"stock_quantity": 7, "stock_status": "in_stock"},
    "10098437960190250": {"stock_quantity": 1, "stock_status": "low_stock"},
    "29934692319448320": {"stock_quantity": 10, "stock_status": "in_stock"},
    "29721762554073939": {"stock_quantity": 4, "stock_status": "low_stock"},
    "9533864750054764": {"stock_quantity": 6, "stock_status": "in_stock"},
    "29767553459502718": {"stock_quantity": 0, "stock_status": "out_of_stock"}
}

category_cache = {
    "Dry Spices": ["29731645503115608", "9754687801263091", "9715602025185036", "9536779646410457", "9610090482419920", "29392834080360744", "29180309118279910", "9560808797375497", "29239261912387560", "29368899942725277"],
    "Wet Spices": ["30331860066413533", "9130680133704059", "23939808892293564", "9674011849346532", "10098437960190250"], 
    # "Herb Spices": [],
}


product_options_cache = {
    "29731645503115608": ["29934692319448320", "29721762554073939", "29767553459502718", "9533864750054764"],
    "9754687801263091": ["30331860066413533", "9130680133704059", "23939808892293564", "9674011849346532", "29934692319448320", "29721762554073939"],
    "9715602025185036": ["29934692319448320", "29721762554073939", "29767553459502718", "9533864750054764", "10098437960190250"]
}

# Mock category data
MOCK_CATEGORIES = [
    {
        "name": "Electronics",
        "image_id": "1234567890",
        "description": "Laptops, smartphones, and gadgets",
        "product_count": 45
    },
    {
        "name": "Clothing",
        "image_id": "2345678901",
        "description": "Fashion for men and women",
        "product_count": 78
    },
    {
        "name": "Home & Kitchen",
        "image_id": "3456789012",
        "description": "Furniture and appliances",
        "product_count": 63
    },
    {
        "name": "Beauty",
        "image_id": "4567890123",
        "description": "Makeup and skincare products",
        "product_count": 32
    },
    {
        "name": "Books",
        "image_id": "5678901234",
        "description": "Fiction and non-fiction books",
        "product_count": 104
    },
    {
        "name": "Sports",
        "image_id": "6789012345",
        "description": "Sports equipment and apparel",
        "product_count": 51
    },
    {
        "name": "Toys",
        "image_id": "7890123456",
        "description": "Games and toys for all ages",
        "product_count": 39
    },
    {
        "name": "Jewelry",
        "image_id": "8901234567",
        "description": "Necklaces, rings, and watches",
        "product_count": 27
    },
    {
        "name": "Grocery",
        "image_id": "9012345678",
        "description": "Food and household essentials",
        "product_count": 85
    },
    {
        "name": "Health",
        "image_id": "0123456789",
        "description": "Supplements and wellness products",
        "product_count": 42
    },
]

# Mock saved mobile money accounts
MOCK_PAYMENT_ACCOUNTS = [
    {
        "id": "momo1",
        "network": "MTN",
        "number": "0241234567",
        "name": "John Doe",
        "is_default": True,
        "last_used": "2025-03-15T14:30:45"
    },
    {
        "id": "momo2",
        "network": "Vodafone",
        "number": "0501234567",
        "name": "John Doe",
        "is_default": False,
        "last_used": "2025-02-28T09:12:33"
    },
    {
        "id": "momo3",
        "network": "AirtelTigo",
        "number": "0271234567",
        "name": "John Doe",
        "is_default": False,
        "last_used": "2025-01-10T16:45:21"
    }
]

# Mock saved shipping addresses
MOCK_SHIPPING_ADDRESSES = [
    {
        "id": "addr1",
        "name": "Home",
        "recipient": "John Doe",
        "street": "123 Independence Avenue",
        "city": "Accra",
        "region": "Greater Accra",
        "phone": "0241234567",
        "is_default": True,
        "last_used": "2025-03-20T11:25:10"
    },
    {
        "id": "addr2",
        "name": "Office",
        "recipient": "John Doe",
        "street": "45 Liberation Road",
        "city": "Accra",
        "region": "Greater Accra",
        "phone": "0501234567",
        "is_default": False,
        "last_used": "2025-02-14T14:30:22"
    },
    {
        "id": "addr3",
        "name": "Friend's Place",
        "recipient": "Jane Smith",
        "street": "78 Cantonments Road",
        "city": "Accra",
        "region": "Greater Accra",
        "phone": "0271234567",
        "is_default": False,
        "last_used": "2025-01-05T09:10:45"
    }
]

# List of available mobile money networks in Ghana
MOBILE_MONEY_NETWORKS = ["MTN", "Vodafone", "AirtelTigo"]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('whatsapp_store')


