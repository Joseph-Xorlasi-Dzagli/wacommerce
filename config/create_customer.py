# import firebase_admin
# from firebase_admin import credentials, firestore
# from datetime import datetime

# # Initialize Firebase (if not already initialized)
# try:
#     # Use your existing Firebase credentials
#     cred = credentials.Certificate('firebase-credentials.json')
#     firebase_admin.initialize_app(cred, {'projectId': 'apsel-c9e99'})
# except:
#     pass  # Already initialized



from datetime import datetime
import os
from dotenv import load_dotenv
import logging
import firebase_admin
from firebase_admin import credentials, firestore

# Load environment variables
load_dotenv()

# API credentials
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
BUSINESS_ACCOUNT_ID = os.getenv("BUSINESS_ACCOUNT_ID")
CATALOG_ID = os.getenv("CATALOG_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BUSINESS_ID = os.getenv("BUSINESS_ID", "default_business")

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

# Initialize Firestore
db = firestore.client()

def create_customer_with_payment():
    """Create customer with all fields populated"""
    
    customer_id = "233206252066"  # Using WhatsApp number as customer ID
    business_id = "test_business"  # Replace with your actual business ID
    
    # Customer data with all fields populated
    customer_data = {
        "business_id": business_id,
        "name": "joexorlasi",
        "email": "joexorlasi@example.com",
        "phone": "233206252066",
        "whatsapp_number": "233206252066",
        "whatsapp_name": "joexorlasi",
        "location": "Accra, Ghana",
        "coordinates": firestore.GeoPoint(5.6037, -0.1870),  # Accra coordinates
        "status": "active",
        "notes": "Regular customer, prefers WhatsApp communication",
        "avatar_url": "https://example.com/avatars/joexorlasi.jpg",
        "preferred_payment_method": "momo",
        "saved_addresses": ["addr1", "addr2"],  # Array of address IDs
        "last_whatsapp_interaction": datetime.now(),
        "total_whatsapp_orders": 0,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "payment_accounts": ["0206252066acc1"]
    }
    
    try:
        # Create customer document
        customer_ref = db.collection('customers').document(customer_id)
        customer_ref.set(customer_data)
        
        print(f"✅ Successfully created customer: {customer_id}")
        print(f"   Name: {customer_data['name']}")
        print(f"   Email: {customer_data['email']}")
        print(f"   Phone: {customer_data['phone']}")
        print(f"   WhatsApp: {customer_data['whatsapp_number']}")
        print(f"   WhatsApp Name: {customer_data['whatsapp_name']}")
        print(f"   Location: {customer_data['location']}")
        print(f"   Coordinates: {customer_data['coordinates']}")
        print(f"   Status: {customer_data['status']}")
        print(f"   Notes: {customer_data['notes']}")
        print(f"   Avatar URL: {customer_data['avatar_url']}")
        print(f"   Preferred Payment: {customer_data['preferred_payment_method']}")
        print(f"   Saved Addresses: {customer_data['saved_addresses']}")
        print(f"   Last WhatsApp Interaction: {customer_data['last_whatsapp_interaction']}")
        print(f"   Total WhatsApp Orders: {customer_data['total_whatsapp_orders']}")
        print(f"   Payment Accounts: {customer_data['payment_accounts']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating customer: {str(e)}")
        return False

def create_customer_addresses():
    """Create sample customer addresses"""
    
    customer_id = "233206252066"
    business_id = "test_business"
    
    # Address 1 - Home
    address1_data = {
        "customer_id": customer_id,
        "business_id": business_id,
        "name": "Home",
        "recipient": "joexorlasi",
        "street": "123 Independence Avenue",
        "city": "Accra",
        "region": "Greater Accra",
        "country": "Ghana",
        "postal_code": "GA-123-4567",
        "phone": "233206252066",
        "coordinates": firestore.GeoPoint(5.6037, -0.1870),
        "delivery_instructions": "Gate is blue, ring bell twice",
        "is_default": True,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "last_used": datetime.now()
    }
    
    # Address 2 - Office
    address2_data = {
        "customer_id": customer_id,
        "business_id": business_id,
        "name": "Office",
        "recipient": "joexorlasi",
        "street": "45 Liberation Road",
        "city": "Accra",
        "region": "Greater Accra",
        "country": "Ghana",
        "postal_code": "GA-456-7890",
        "phone": "233501234567",
        "coordinates": firestore.GeoPoint(5.6108, -0.1859),
        "delivery_instructions": "Reception on ground floor, ask for joexorlasi",
        "is_default": False,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "last_used": datetime.fromisoformat("2025-02-15T10:30:00")
    }
    
    try:
        # Create address documents
        address1_ref = db.collection('customer_addresses').document('addr1')
        address1_ref.set(address1_data)
        
        address2_ref = db.collection('customer_addresses').document('addr2')
        address2_ref.set(address2_data)
        
        print(f"✅ Successfully created address: addr1 (Home)")
        print(f"   Recipient: {address1_data['recipient']}")
        print(f"   Street: {address1_data['street']}")
        print(f"   City: {address1_data['city']}, {address1_data['region']}")
        print(f"   Phone: {address1_data['phone']}")
        print(f"   Instructions: {address1_data['delivery_instructions']}")
        print(f"   Default: {address1_data['is_default']}")
        
        print(f"✅ Successfully created address: addr2 (Office)")
        print(f"   Recipient: {address2_data['recipient']}")
        print(f"   Street: {address2_data['street']}")
        print(f"   City: {address2_data['city']}, {address2_data['region']}")
        print(f"   Phone: {address2_data['phone']}")
        print(f"   Instructions: {address2_data['delivery_instructions']}")
        print(f"   Default: {address2_data['is_default']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating addresses: {str(e)}")
        return False

def create_separate_payment_account():
    """Create separate payment account in payment_accounts collection"""
    
    customer_id = "233206252066"
    business_id = "test_business"
    
    payment_data = {
        "customer_id": customer_id,
        "business_id": business_id,
        "account_number": "0501234567",
        "account_holder": "John Doe",
        "account_provider": "Vodafone",
        "account_type": "mobile_money",
        "is_default": True,
        "last_used": datetime.fromisoformat("2025-02-28T09:12:33"),
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    
    try:
        # Create payment account document
        # Create address documents
        payment_ref = db.collection('payment_accounts').document('0206252066acc1')
        payment_ref.set(payment_data)
        
        print(f"✅ Successfully created payment account: {payment_ref.id}")
        print(f"   Customer: {payment_data['customer_id']}")
        print(f"   Account Number: {payment_data['account_number']}")
        print(f"   Account Holder: {payment_data['account_holder']}")
        print(f"   Provider: {payment_data['account_provider']}")
        print(f"   Type: {payment_data['account_type']}")
        print(f"   Default: {payment_data['is_default']}")
        print(f"   Last Used: {payment_data['last_used']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating payment account: {str(e)}")
        return False

def verify_customer_creation(customer_id):
    """Verify the customer was created successfully"""
    try:
        customer_ref = db.collection('customers').document(customer_id)
        customer_doc = customer_ref.get()
        
        if customer_doc.exists:
            data = customer_doc.to_dict()
            print(f"\n📋 Customer Verification:")
            print(f"   Document ID: {customer_doc.id}")
            print(f"   Business ID: {data.get('business_id')}")
            print(f"   Name: {data.get('name')}")
            print(f"   Email: {data.get('email')}")
            print(f"   Phone: {data.get('phone')}")
            print(f"   WhatsApp Number: {data.get('whatsapp_number')}")
            print(f"   WhatsApp Name: {data.get('whatsapp_name')}")
            print(f"   Location: {data.get('location')}")
            print(f"   Coordinates: {data.get('coordinates')}")
            print(f"   Status: {data.get('status')}")
            print(f"   Notes: {data.get('notes')}")
            print(f"   Avatar URL: {data.get('avatar_url')}")
            print(f"   Preferred Payment Method: {data.get('preferred_payment_method')}")
            print(f"   Saved Addresses: {data.get('saved_addresses')}")
            print(f"   Last WhatsApp Interaction: {data.get('last_whatsapp_interaction')}")
            print(f"   Total WhatsApp Orders: {data.get('total_whatsapp_orders')}")
            print(f"   Created At: {data.get('created_at')}")
            print(f"   Updated At: {data.get('updated_at')}")
            
            payment_account = data.get('payment_account', {})
            if payment_account:
                print(f"   Payment Account Provider: {payment_account.get('provider')}")
                print(f"   Payment Account Number: {payment_account.get('account_number')}")
                print(f"   Payment Account Name: {payment_account.get('account_name')}")
                print(f"   Payment Account Default: {payment_account.get('is_default')}")
                print(f"   Payment Account Last Used: {payment_account.get('last_used')}")
            
            return True
        else:
            print(f"❌ Customer {customer_id} not found")
            return False
            
    except Exception as e:
        print(f"❌ Error verifying customer: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Creating comprehensive customer data...")
    
    # Create the customer with embedded payment account
    print("\n1️⃣ Creating customer with embedded payment account...")
    # success = create_customer_with_payment()
    create_separate_payment_account()

    
    # if success:
    #     # Create customer addresses
    #     print("\n2️⃣ Creating customer addresses...")
    #     create_customer_addresses()
        
    #     # Create separate payment account (optional)
    #     print("\n3️⃣ Creating separate payment account...")
    #     create_separate_payment_account()
        
    #     # Verify creation
    #     print("\n4️⃣ Verifying customer creation...")
    #     verify_customer_creation("233206252066")
    
    print("\n✨ Script completed!")