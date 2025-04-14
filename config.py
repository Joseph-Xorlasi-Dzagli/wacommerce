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

# In-memory storage (will be replaced with proper database in production)
# These are initialized here to be shared across modules
sessions = {}
orders = []
product_cache = {}
# category_cache = {}
category_cache = {
    "electronics": ["9686994108029742","10029798880373213","9405022489615254","9019634074831244","9874487352584680","10077300928955678"],
    "clothing": ["9686994108029742","10029798880373213","9405022489615254","9019634074831244","9874487352584680","10077300928955678"],
    "home": ["9686994108029742","10029798880373213","9405022489615254","9019634074831244","9874487352584680","10077300928955678"],
    "books": ["9686994108029742","10029798880373213","9405022489615254","9019634074831244","9874487352584680","10077300928955678"],
    "sports": ["9686994108029742","10029798880373213","9405022489615254","9019634074831244","9874487352584680","10077300928955678"],
    "beauty": ["9686994108029742","10029798880373213","9405022489615254","9019634074831244","9874487352584680","10077300928955678"],
    "toys": ["9686994108029742","10029798880373213","9405022489615254","9019634074831244","9874487352584680","10077300928955678"],
    "grocery": ["9686994108029742","10029798880373213","9405022489615254","9019634074831244","9874487352584680","10077300928955678"],
    "automotive": ["9686994108029742","10029798880373213","9405022489615254","9019634074831244","9874487352584680","10077300928955678"],
    "garden": ["9686994108029742","10029798880373213","9405022489615254","9019634074831244","9874487352584680","10077300928955678"]
}

product_options_cache = {
    "9686994108029742": ["9686994108029742","10029798880373213","9405022489615254","9019634074831244","9874487352584680","10077300928955678"],
    "10029798880373213": ["9686994108029742","10029798880373213","9405022489615254","9019634074831244","9874487352584680","10077300928955678"],
    "9405022489615254": ["9686994108029742","10029798880373213","9405022489615254","9019634074831244","9874487352584680","10077300928955678"],
    "9019634074831244": ["9686994108029742","10029798880373213","9405022489615254","9019634074831244","9874487352584680","10077300928955678"],
    "9874487352584680": ["9686994108029742","10029798880373213","9405022489615254","9019634074831244","9874487352584680","10077300928955678"],
    "10077300928955678": ["9686994108029742","10029798880373213","9405022489615254","9019634074831244","9874487352584680","10077300928955678"],
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