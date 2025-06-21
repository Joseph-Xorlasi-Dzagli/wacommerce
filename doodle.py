import uuid
from datetime import datetime
from utils.logger import get_logger
from config import sessions

logger = get_logger(__name__)

try:
    from database.firebase_database import firebase_db
    FIREBASE_AVAILABLE = True
except ImportError:
    logger.warning("Firebase not available, using mock data")
    FIREBASE_AVAILABLE = False

def get_customer_payment_accounts(user_id):
    """Get customer's saved payment accounts from database"""
    try:
        if not FIREBASE_AVAILABLE:
            logger.warning("Firebase not available, returning empty payment accounts")
            return []
        
        # Query payment accounts for this customer
        accounts_ref = firebase_db.db.collection('payment_accounts')
        query = accounts_ref.where('customer_id', '==', user_id).order_by('last_used', direction='DESCENDING')
        
        accounts = []
        for doc in query.stream():
            account_data = doc.to_dict()
            account_data['id'] = doc.id
            accounts.append(account_data)
        
        logger.info(f"Retrieved {len(accounts)} payment accounts for user {user_id}")
        return accounts
        
    except Exception as e:
        logger.error(f"Error fetching payment accounts for user {user_id}: {str(e)}")
        return []

def save_customer_payment_account(user_id, network, number, name, business_id=None):
    """Save a new payment account for the customer"""
    try:
        if not FIREBASE_AVAILABLE:
            logger.warning("Firebase not available, cannot save payment account")
            return None
        
        # Check if account already exists
        existing_accounts = get_customer_payment_accounts(user_id)
        for account in existing_accounts:
            if account.get('account_number') == number and account.get('account_provider') == network:
                logger.info(f"Payment account already exists for {number} ({network})")
                return account['id']
        
        # Create new payment account
        account_data = {
            'customer_id': user_id,
            'business_id': business_id or 'default_business',
            'account_number': number,
            'account_holder': name,
            'account_provider': network,
            'account_type': 'mobile_money',
            'is_default': len(existing_accounts) == 0,  # First account is default
            'last_used': firebase_db.db.SERVER_TIMESTAMP,
            'created_at': firebase_db.db.SERVER_TIMESTAMP,
            'updated_at': firebase_db.db.SERVER_TIMESTAMP
        }
        
        # Add to database
        doc_ref = firebase_db.db.collection('payment_accounts').add(account_data)
        account_id = doc_ref[1].id
        
        logger.info(f"Saved payment account {account_id} for user {user_id}")
        return account_id
        
    except Exception as e:
        logger.error(f"Error saving payment account for user {user_id}: {str(e)}")
        return None

def get_customer_addresses(user_id):
    """Get customer's saved addresses from database"""
    try:
        if not FIREBASE_AVAILABLE:
            logger.warning("Firebase not available, returning empty addresses")
            return []
        
        # Query addresses for this customer
        addresses_ref = firebase_db.db.collection('customer_addresses')
        query = addresses_ref.where('customer_id', '==', user_id).order_by('last_used', direction='DESCENDING')
        
        addresses = []
        for doc in query.stream():
            address_data = doc.to_dict()
            address_data['id'] = doc.id
            addresses.append(address_data)
        
        logger.info(f"Retrieved {len(addresses)} addresses for user {user_id}")
        return addresses
        
    except Exception as e:
        logger.error(f"Error fetching addresses for user {user_id}: {str(e)}")
        return []

def save_customer_address(user_id, address_text, name, business_id=None):
    """Save a new address for the customer"""
    try:
        if not FIREBASE_AVAILABLE:
            logger.warning("Firebase not available, cannot save address")
            return None
        
        # Parse address text (basic parsing - you can enhance this)
        lines = address_text.strip().split('\n')
        recipient = lines[0] if len(lines) > 0 else "Customer"
        street = lines[1] if len(lines) > 1 else address_text
        city = "Accra"  # Default city
        region = "Greater Accra"  # Default region
        phone = user_id  # Use WhatsApp number as default
        
        # Try to extract city and region from address
        for line in lines:
            if any(city_name in line.lower() for city_name in ['accra', 'kumasi', 'tamale', 'cape coast']):
                parts = line.split(',')
                if len(parts) >= 2:
                    city = parts[0].strip()
                    region = parts[1].strip()
                break
        
        # Check existing addresses to avoid duplicates
        existing_addresses = get_customer_addresses(user_id)
        
        # Create new address
        address_data = {
            'customer_id': user_id,
            'business_id': business_id or 'default_business',
            'name': name,
            'recipient': recipient,
            'street': street,
            'city': city,
            'region': region,
            'country': 'Ghana',
            'postal_code': '',
            'phone': phone,
            'delivery_instructions': '',
            'is_default': len(existing_addresses) == 0,  # First address is default
            'created_at': firebase_db.db.SERVER_TIMESTAMP,
            'updated_at': firebase_db.db.SERVER_TIMESTAMP,
            'last_used': firebase_db.db.SERVER_TIMESTAMP
        }
        
        # Add coordinates if available (from location sharing)
        if 'coordinates:' in address_text.lower():
            # Extract coordinates from location text
            try:
                coord_line = [line for line in lines if 'coordinates:' in line.lower()][0]
                coords = coord_line.split(':', 1)[1].strip().split(',')
                if len(coords) == 2:
                    lat = float(coords[0].strip())
                    lng = float(coords[1].strip())
                    address_data['coordinates'] = firebase_db.db.GeoPoint(lat, lng)
            except Exception as coord_error:
                logger.warning(f"Could not parse coordinates: {str(coord_error)}")
        
        # Add to database
        doc_ref = firebase_db.db.collection('customer_addresses').add(address_data)
        address_id = doc_ref[1].id
        
        logger.info(f"Saved address {address_id} for user {user_id}")
        return address_id
        
    except Exception as e:
        logger.error(f"Error saving address for user {user_id}: {str(e)}")
        return None

def get_or_create_customer(user_id, name=None, business_id=None):
    """Get existing customer or create new one"""
    try:
        if not FIREBASE_AVAILABLE:
            logger.warning("Firebase not available, cannot manage customers")
            return None
        
        # Check if customer exists
        customers_ref = firebase_db.db.collection('customers')
        query = customers_ref.where('whatsapp_number', '==', user_id)
        
        existing_customers = list(query.stream())
        
        if existing_customers:
            # Customer exists, update last interaction
            customer_doc = existing_customers[0]
            customer_data = customer_doc.to_dict()
            customer_data['id'] = customer_doc.id
            
            # Update last interaction
            customer_doc.reference.update({
                'last_whatsapp_interaction': firebase_db.db.SERVER_TIMESTAMP,
                'updated_at': firebase_db.db.SERVER_TIMESTAMP
            })
            
            logger.info(f"Found existing customer {customer_data['id']} for user {user_id}")
            return customer_data
        else:
            # Create new customer
            customer_data = {
                'business_id': business_id or 'default_business',
                'name': name or 'Customer',
                'email': '',
                'phone': user_id,
                'whatsapp_number': user_id,
                'whatsapp_name': name or 'Customer',
                'location': '',
                'status': 'active',
                'notes': f'Customer created via WhatsApp on {datetime.now().isoformat()}',
                'avatar_url': '',
                'preferred_payment_method': '',
                'saved_addresses': [],
                'last_whatsapp_interaction': firebase_db.db.SERVER_TIMESTAMP,
                'total_whatsapp_orders': 0,
                'created_at': firebase_db.db.SERVER_TIMESTAMP,
                'updated_at': firebase_db.db.SERVER_TIMESTAMP
            }
            
            doc_ref = firebase_db.db.collection('customers').add(customer_data)
            customer_id = doc_ref[1].id
            customer_data['id'] = customer_id
            
            logger.info(f"Created new customer {customer_id} for user {user_id}")
            return customer_data
            
    except Exception as e:
        logger.error(f"Error managing customer for user {user_id}: {str(e)}")
        return None

def update_customer_payment_method(user_id, payment_method):
    """Update customer's preferred payment method"""
    try:
        if not FIREBASE_AVAILABLE:
            return False
        
        customers_ref = firebase_db.db.collection('customers')
        query = customers_ref.where('whatsapp_number', '==', user_id)
        
        for doc in query.stream():
            doc.reference.update({
                'preferred_payment_method': payment_method,
                'updated_at': firebase_db.db.SERVER_TIMESTAMP
            })
            return True
        
        logger.warning(f"No customer found to update payment method for user {user_id}")
        return False
        
    except Exception as e:
        logger.error(f"Error updating payment method for user {user_id}: {str(e)}")
        return False

def get_customer_by_whatsapp(user_id):
    """Get customer by WhatsApp number"""
    try:
        if not FIREBASE_AVAILABLE:
            return None
        
        customers_ref = firebase_db.db.collection('customers')
        query = customers_ref.where('whatsapp_number', '==', user_id).limit(1)
        
        for doc in query.stream():
            customer_data = doc.to_dict()
            customer_data['id'] = doc.id
            return customer_data
        
        return None
        
    except Exception as e:
        logger.error(f"Error fetching customer by WhatsApp {user_id}: {str(e)}")
        return None