import uuid
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)

# Import Firebase database
try:
    from config import db
    FIREBASE_AVAILABLE = db is not None
    if not FIREBASE_AVAILABLE:
        logger.warning("Firebase database not available in config")
except ImportError as e:
    logger.error(f"Failed to import Firebase database: {str(e)}")
    FIREBASE_AVAILABLE = False
    db = None

def get_customer_payment_accounts(business_context, user_id):
    """Get customer's saved payment accounts from database"""
    try:
        if not FIREBASE_AVAILABLE or not db:
            logger.warning("Firebase not available, returning empty payment accounts")
            return []
        
        business_id = business_context.get('business_id')
        db_instance = business_context.get('db', db)
        
        # Import here to avoid circular imports
        from firebase_admin import firestore
        
        # First get customer ID
        customer = get_customer_by_whatsapp_internal(db_instance, user_id, business_id)
        if not customer:
            return []
        
        customer_id = customer.get('id')
        
        # Query payment accounts for this customer and business
        accounts_ref = db_instance.collection('payment_accounts').where(
            filter=firestore.FieldFilter('customer_id', '==', customer_id)
        ).where(
            filter=firestore.FieldFilter('business_id', '==', business_id)
        ).order_by('last_used', direction=firestore.Query.DESCENDING)
        
        accounts = []
        for doc in accounts_ref.get():
            account_data = doc.to_dict()
            account_data['id'] = doc.id
            accounts.append(account_data)
        
        logger.info(f"Retrieved {len(accounts)} payment accounts for user {user_id} in business {business_id}")
        return accounts
        
    except Exception as e:
        logger.error(f"Error fetching payment accounts for user {user_id}: {str(e)}")
        return []

def save_customer_payment_account(business_context, user_id, network, number, name):
    """Save a new payment account for the customer"""
    try:
        if not FIREBASE_AVAILABLE or not db:
            logger.warning("Firebase not available, cannot save payment account")
            return None
        
        # Import here to avoid circular imports
        from firebase_admin import firestore
        
        business_id = business_context.get('business_id')
        db_instance = business_context.get('db', db)
        
        # Get or create customer
        customer = get_or_create_customer(business_context, user_id, name)
        if not customer:
            return None
        
        customer_id = customer.get('id')
        
        # Check if account already exists for this customer and business
        existing_accounts = get_customer_payment_accounts(business_context, user_id)
        for account in existing_accounts:
            if (account.get('account_number') == number and 
                account.get('account_provider') == network and
                account.get('business_id') == business_id):
                logger.info(f"Payment account already exists for {number} ({network}) in business {business_id}")
                # Update last used
                account_ref = db_instance.collection('payment_accounts').document(account['id'])
                account_ref.update({'last_used': firestore.SERVER_TIMESTAMP})
                return account['id']
        
        # Create new payment account
        account_data = {
            'customer_id': customer_id,
            'business_id': business_id,
            'account_number': number,
            'account_holder': name,
            'account_provider': network,
            'account_type': 'mobile_money',
            'is_default': len(existing_accounts) == 0,  # First account is default
            'last_used': firestore.SERVER_TIMESTAMP,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        
        # Add to database
        doc_ref = db_instance.collection('payment_accounts').add(account_data)
        account_id = doc_ref[1].id
        
        logger.info(f"Saved payment account {account_id} for user {user_id} in business {business_id}")
        return account_id
        
    except Exception as e:
        logger.error(f"Error saving payment account for user {user_id}: {str(e)}")
        return None

def get_customer_addresses(business_context, user_id):
    """Get customer's saved addresses from database"""
    try:
        if not FIREBASE_AVAILABLE or not db:
            logger.warning("Firebase not available, returning empty addresses")
            return []
        
        business_id = business_context.get('business_id')
        db_instance = business_context.get('db', db)
        
        # Import here to avoid circular imports
        from firebase_admin import firestore
        
        # First get customer ID
        customer = get_customer_by_whatsapp_internal(db_instance, user_id, business_id)
        if not customer:
            return []
        
        customer_id = customer.get('id')
        
        # Query addresses for this customer and business
        addresses_ref = db_instance.collection('customer_addresses').where(
            filter=firestore.FieldFilter('customer_id', '==', customer_id)
        ).where(
            filter=firestore.FieldFilter('business_id', '==', business_id)
        ).order_by('last_used', direction=firestore.Query.DESCENDING)
        
        addresses = []
        for doc in addresses_ref.get():
            address_data = doc.to_dict()
            address_data['id'] = doc.id
            addresses.append(address_data)
        
        logger.info(f"Retrieved {len(addresses)} addresses for user {user_id} in business {business_id}")
        return addresses
        
    except Exception as e:
        logger.error(f"Error fetching addresses for user {user_id}: {str(e)}")
        return []

def save_customer_address(business_context, user_id, address_text, name):
    """Save a new address for the customer"""
    try:
        if not FIREBASE_AVAILABLE or not db:
            logger.warning("Firebase not available, cannot save address")
            return None
        
        # Import here to avoid circular imports
        from firebase_admin import firestore
        
        business_id = business_context.get('business_id')
        db_instance = business_context.get('db', db)
        
        # Get or create customer
        customer = get_or_create_customer(business_context, user_id, name)
        if not customer:
            return None
        
        customer_id = customer.get('id')
        
        address_data = {}
        
        # Handle location data from geocoding API
        if isinstance(address_text, dict):
            lat = address_text.get('lat', '')
            lng = address_text.get('lon', '')
            
            # Ensure lat and lng are floats, or raise a meaningful error
            try:
                lat = float(lat)
                lng = float(lng)
            except (TypeError, ValueError):
                logger.error(f"Invalid latitude or longitude for user {user_id}: lat={lat}, lng={lng}")
                return None
            
            address_details = address_text.get('address', {})
            
            # Extract address components
            recipient = customer.get('name', 'Customer')
            street = address_details.get('road', '') or address_details.get('street', '')
            suburb = address_details.get('suburb', '')
            city = address_details.get('city', 'Accra')
            region = address_details.get('state', 'Greater Accra')
            country = address_details.get('country', 'Ghana')
            postal_code = address_details.get('postcode', '')
            phone = user_id  # Use WhatsApp number as default
            
            # Create formatted name if not provided
            if not name or name == "Location Address":
                name_parts = []
                if address_details.get('neighbourhood'):
                    name_parts.append(address_details['neighbourhood'])
                if address_details.get('road'):
                    name_parts.append(address_details['road'])
                if address_details.get('house_number'):
                    name_parts.append(address_details['house_number'])
                name = ' '.join(name_parts) or "Shared Location"
            
            address_data = {
                'customer_id': customer_id,
                'business_id': business_id,
                'name': name,
                'recipient': recipient,
                'street': street,
                'suburb': suburb,
                'city': city,
                'region': region,
                'country': country,
                'postal_code': postal_code,
                'phone': phone,
                'delivery_instructions': '',
                'is_default': False,
                'coordinates': firestore.GeoPoint(lat, lng),
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP,
                'last_used': firestore.SERVER_TIMESTAMP
            }
        else:
            # Handle string address
            recipient = customer.get('name', 'Customer')
            address_data = {
                'customer_id': customer_id,
                'business_id': business_id,
                'name': name or 'Manual Address',
                'recipient': recipient,
                'street': str(address_text),
                'suburb': '',
                'city': '',
                'region': '',
                'country': '',
                'postal_code': '',
                'phone': user_id,
                'delivery_instructions': '',
                'is_default': False,
                'coordinates': None,
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP,
                'last_used': firestore.SERVER_TIMESTAMP
            }
        
        # Add to database
        doc_ref = db_instance.collection('customer_addresses').add(address_data)
        address_id = doc_ref[1].id
        
        logger.info(f"Saved address {address_id} for user {user_id} in business {business_id}")
        return address_id
        
    except Exception as e:
        logger.error(f"Error saving address for user {user_id}: {str(e)}")
        return None

def get_or_create_customer(business_context, user_id, name=None):
    """Get existing customer or create new one"""
    try:
        if not FIREBASE_AVAILABLE or not db:
            logger.warning("Firebase not available, cannot manage customers")
            return None
        
        # Import here to avoid circular imports
        from firebase_admin import firestore
        
        business_id = business_context.get('business_id')
        db_instance = business_context.get('db', db)
        
        # Check if customer exists for this business
        customers_ref = db_instance.collection('customers')
        query = customers_ref.where(
            filter=firestore.FieldFilter('whatsapp_number', '==', user_id)
        ).where(
            filter=firestore.FieldFilter('business_id', '==', business_id)
        ).limit(1)
        
        existing_customers = list(query.get())
        
        if existing_customers:
            # Customer exists, update last interaction
            customer_doc = existing_customers[0]
            customer_data = customer_doc.to_dict()
            customer_data['id'] = customer_doc.id
            
            # Update last interaction
            customer_doc.reference.update({
                'last_whatsapp_interaction': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Found existing customer {customer_data['id']} for user {user_id} in business {business_id}")
            return customer_data
        else:
            # Create new customer
            customer_data = {
                'business_id': business_id,
                'name': name or 'Customer',
                'email': '',
                'phone': user_id,
                'whatsapp_number': user_id,
                'whatsapp_name': name or 'Customer',
                'location': '',
                'coordinates': None,
                'status': 'active',
                'notes': f'Customer created via WhatsApp on {datetime.now().isoformat()}',
                'avatar_url': '',
                'preferred_payment_method': '',
                'saved_addresses': [],
                'last_whatsapp_interaction': firestore.SERVER_TIMESTAMP,
                'total_whatsapp_orders': 0,
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            doc_ref = db_instance.collection('customers').add(customer_data)
            customer_id = doc_ref[1].id
            customer_data['id'] = customer_id
            
            logger.info(f"Created new customer {customer_id} for user {user_id} in business {business_id}")
            return customer_data
            
    except Exception as e:
        logger.error(f"Error managing customer for user {user_id}: {str(e)}")
        return None

def update_customer_payment_method(business_context, user_id, payment_method):
    """Update customer's preferred payment method"""
    try:
        if not FIREBASE_AVAILABLE or not db:
            return False
        
        # Import here to avoid circular imports
        from firebase_admin import firestore
        
        business_id = business_context.get('business_id')
        db_instance = business_context.get('db', db)
        
        customers_ref = db_instance.collection('customers')
        query = customers_ref.where(
            filter=firestore.FieldFilter('whatsapp_number', '==', user_id)
        ).where(
            filter=firestore.FieldFilter('business_id', '==', business_id)
        )
        
        for doc in query.get():
            doc.reference.update({
                'preferred_payment_method': payment_method,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            return True
        
        logger.warning(f"No customer found to update payment method for user {user_id} in business {business_id}")
        return False
        
    except Exception as e:
        logger.error(f"Error updating payment method for user {user_id}: {str(e)}")
        return False

def get_customer_by_whatsapp_internal(db_instance, user_id, business_id):
    """Internal function to get customer by WhatsApp number with specific db instance"""
    try:
        if not FIREBASE_AVAILABLE or not db_instance:
            return None
        
        # Import here to avoid circular imports
        from firebase_admin import firestore
        
        customers_ref = db_instance.collection('customers')
        query = customers_ref.where(
            filter=firestore.FieldFilter('whatsapp_number', '==', user_id)
        ).where(
            filter=firestore.FieldFilter('business_id', '==', business_id)
        ).limit(1)
        
        for doc in query.get():
            customer_data = doc.to_dict()
            customer_data['id'] = doc.id
            return customer_data
        
        return None
        
    except Exception as e:
        logger.error(f"Error fetching customer by WhatsApp {user_id} in business {business_id}: {str(e)}")
        return None

def get_business_customers(business_context, limit=50):
    """Get all customers for a business"""
    db_instance = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db_instance or not business_id:
        return []
    
    try:
        from firebase_admin import firestore
        
        customers_ref = db_instance.collection('customers').where(
            filter=firestore.FieldFilter('business_id', '==', business_id)
        ).order_by('last_whatsapp_interaction', direction=firestore.Query.DESCENDING).limit(limit)
        
        customers = customers_ref.get()
        
        customer_list = []
        for customer_doc in customers:
            customer_data = customer_doc.to_dict()
            customer_data['id'] = customer_doc.id
            customer_list.append(customer_data)
        
        return customer_list
        
    except Exception as e:
        logger.error(f"Error getting business customers: {str(e)}")
        return []

def update_customer_profile(business_context, user_id, profile_data):
    """Update customer profile information"""
    db_instance = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db_instance or not business_id:
        return False
    
    try:
        customer = get_customer_by_whatsapp_internal(db_instance, user_id, business_id)
        if not customer:
            return False
        
        customer_id = customer.get('id')
        
        # Import here to avoid circular imports
        from firebase_admin import firestore
        
        # Update customer data
        update_data = {
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        
        # Add fields that are provided
        allowed_fields = ['name', 'email', 'location', 'notes', 'preferred_payment_method']
        for field in allowed_fields:
            if field in profile_data:
                update_data[field] = profile_data[field]
        
        customer_ref = db_instance.collection('customers').document(customer_id)
        customer_ref.update(update_data)
        
        logger.info(f"Updated customer profile for {customer_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating customer profile: {str(e)}")
        return False

def delete_customer_data(business_context, user_id):
    """Delete all customer data for a business (GDPR compliance)"""
    db_instance = business_context.get('db')
    business_id = business_context.get('business_id')
    
    if not db_instance or not business_id:
        return False
    
    try:
        from firebase_admin import firestore
        
        customer = get_customer_by_whatsapp_internal(db_instance, user_id, business_id)
        if not customer:
            return True  # Already deleted
        
        customer_id = customer.get('id')
        
        # Delete customer addresses
        addresses_ref = db_instance.collection('customer_addresses').where('customer_id', '==', customer_id)
        addresses = addresses_ref.get()
        for address in addresses:
            address.reference.delete()
        
        # Delete payment accounts
        accounts_ref = db_instance.collection('payment_accounts').where('customer_id', '==', customer_id)
        accounts = accounts_ref.get()
        for account in accounts:
            account.reference.delete()
        
        # Delete WhatsApp session
        session_ref = db_instance.collection('whatsapp_sessions').document(f"{business_id}_{user_id}")
        session_ref.delete()
        
        # Anonymize orders (keep for business records but remove personal data)
        orders_ref = db_instance.collection('orders').where('customer.id', '==', customer_id)
        orders = orders_ref.get()
        for order in orders:
            order.reference.update({
                'customer.name': 'Deleted Customer',
                'customer.phone': 'DELETED',
                'customer.whatsapp_number': 'DELETED',
                'shipping_address': 'DELETED',
                'updated_at': firestore.SERVER_TIMESTAMP
            })
        
        # Delete customer record
        customer_ref = db_instance.collection('customers').document(customer_id)
        customer_ref.delete()
        
        logger.info(f"Deleted customer data for {customer_id} in business {business_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting customer data: {str(e)}")
        return False