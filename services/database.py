"""
Database service for Firebase Firestore operations
Handles all database interactions with business context
"""

from config import db, logger
from datetime import datetime
from typing import Dict, List, Optional, Any
import json

class DatabaseService:
    """Service class for database operations with business context"""
    
    def __init__(self):
        self.db = db
        if not self.db:
            raise Exception("Firebase database not initialized")
    
    # Business Configuration Operations
    def get_business_by_phone_id(self, phone_number_id: str) -> Optional[Dict[str, Any]]:
        """Get business configuration by WhatsApp phone number ID"""
        try:
            # Query whatsapp_configs collection
            configs_ref = self.db.collection('whatsapp_configs')
            query = configs_ref.where('phone_number_id', '==', phone_number_id).where('active', '==', True)
            
            results = query.get()
            
            if not results:
                logger.warning(f"No active WhatsApp config found for phone_number_id: {phone_number_id}")
                return None
            
            # Get the first (should be only) result
            config_doc = results[0]
            config_data = config_doc.to_dict()
            
            # Get the business details
            business_id = config_data.get('business_id')
            if not business_id:
                logger.error(f"No business_id found in WhatsApp config: {config_doc.id}")
                return None
            
            business_data = self.get_business_details(business_id)
            if not business_data:
                return None
            
            # Combine business and WhatsApp config
            return {
                'business_id': business_id,
                'business_data': business_data,
                'whatsapp_config': config_data,
                'config_doc_id': config_doc.id
            }
            
        except Exception as e:
            logger.error(f"Error fetching business by phone ID {phone_number_id}: {str(e)}")
            return None
    
    def get_business_details(self, business_id: str) -> Optional[Dict[str, Any]]:
        """Get business details from businesses collection"""
        try:
            business_ref = self.db.collection('businesses').document(business_id)
            business_doc = business_ref.get()
            
            if not business_doc.exists:
                logger.warning(f"Business not found: {business_id}")
                return None
            
            business_data = business_doc.to_dict()
            business_data['id'] = business_id
            
            return business_data
            
        except Exception as e:
            logger.error(f"Error fetching business details {business_id}: {str(e)}")
            return None
    
    def get_business_settings(self, business_id: str) -> Dict[str, Any]:
        """Get business settings with defaults"""
        try:
            settings_ref = self.db.collection('business_settings').document(business_id)
            settings_doc = settings_ref.get()
            
            if settings_doc.exists:
                return settings_doc.to_dict()
            else:
                # Return default settings
                from config import DEFAULT_WHATSAPP_CONFIG, DEFAULT_CHECKOUT_CONFIG
                return {
                    'whatsapp': DEFAULT_WHATSAPP_CONFIG,
                    'checkout': DEFAULT_CHECKOUT_CONFIG,
                    'notifications': {
                        'order_updates': True,
                        'low_stock_alerts': True,
                        'daily_summary': False
                    }
                }
                
        except Exception as e:
            logger.error(f"Error fetching business settings {business_id}: {str(e)}")
            from config import DEFAULT_WHATSAPP_CONFIG, DEFAULT_CHECKOUT_CONFIG
            return {
                'whatsapp': DEFAULT_WHATSAPP_CONFIG,
                'checkout': DEFAULT_CHECKOUT_CONFIG,
                'notifications': {
                    'order_updates': True,
                    'low_stock_alerts': True,
                    'daily_summary': False
                }
            }
    
    def update_business_last_activity(self, business_id: str):
        """Update business last activity timestamp"""
        try:
            business_ref = self.db.collection('businesses').document(business_id)
            business_ref.update({
                'last_whatsapp_activity': datetime.now(),
                'updated_at': datetime.now()
            })
        except Exception as e:
            logger.error(f"Error updating business activity {business_id}: {str(e)}")
    
    # Customer Operations
    def get_or_create_customer(self, business_id: str, whatsapp_number: str, name: str = None) -> str:
        """Get existing customer or create new one"""
        try:
            # Search for existing customer
            customers_ref = self.db.collection('customers')
            query = customers_ref.where('business_id', '==', business_id).where('whatsapp_number', '==', whatsapp_number)
            
            results = query.get()
            
            if results:
                # Customer exists, update last interaction
                customer_doc = results[0]
                customer_ref = customers_ref.document(customer_doc.id)
                customer_ref.update({
                    'last_whatsapp_interaction': datetime.now(),
                    'updated_at': datetime.now()
                })
                
                # Update name if provided and different
                if name and name != customer_doc.to_dict().get('whatsapp_name'):
                    customer_ref.update({'whatsapp_name': name})
                
                return customer_doc.id
            else:
                # Create new customer
                customer_data = {
                    'business_id': business_id,
                    'whatsapp_number': whatsapp_number,
                    'whatsapp_name': name or 'Customer',
                    'name': name or '',
                    'email': '',
                    'phone': whatsapp_number,
                    'status': 'active',
                    'notes': '',
                    'total_whatsapp_orders': 0,
                    'last_whatsapp_interaction': datetime.now(),
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                
                _, customer_ref = customers_ref.add(customer_data)
                logger.info(f"Created new customer {customer_ref.id} for business {business_id}")
                return customer_ref.id
                
        except Exception as e:
            logger.error(f"Error getting/creating customer for business {business_id}, WhatsApp {whatsapp_number}: {str(e)}")
            return None
    
    # Session Operations
    def save_session(self, business_id: str, user_id: str, session_data: Dict[str, Any]):
        """Save WhatsApp session to database"""
        try:
            session_ref = self.db.collection('whatsapp_sessions').document(f"{business_id}_{user_id}")
            
            # Add metadata
            session_data.update({
                'business_id': business_id,
                'user_id': user_id,
                'last_active': datetime.now(),
                'updated_at': datetime.now()
            })
            
            session_ref.set(session_data, merge=True)
            
        except Exception as e:
            logger.error(f"Error saving session for business {business_id}, user {user_id}: {str(e)}")
    
    def get_session(self, business_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get WhatsApp session from database"""
        try:
            session_ref = self.db.collection('whatsapp_sessions').document(f"{business_id}_{user_id}")
            session_doc = session_ref.get()
            
            if session_doc.exists:
                return session_doc.to_dict()
            return None
            
        except Exception as e:
            logger.error(f"Error getting session for business {business_id}, user {user_id}: {str(e)}")
            return None
    
    # Order Operations
    def create_order(self, business_id: str, order_data: Dict[str, Any]) -> Optional[str]:
        """Create new order in database"""
        try:
            # Add business context and timestamps
            order_data.update({
                'business_id': business_id,
                'source': 'whatsapp',
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            })
            
            _, order_ref = self.db.collection('orders').add(order_data)
            logger.info(f"Created order {order_ref.id} for business {business_id}")
            return order_ref.id
            
        except Exception as e:
            logger.error(f"Error creating order for business {business_id}: {str(e)}")
            return None
    
    def get_orders_by_business(self, business_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get orders for a business"""
        try:
            orders_ref = self.db.collection('orders')
            query = orders_ref.where('business_id', '==', business_id).order_by('created_at', direction='DESCENDING').limit(limit)
            
            orders = []
            for doc in query.get():
                order_data = doc.to_dict()
                order_data['id'] = doc.id
                orders.append(order_data)
            
            return orders
            
        except Exception as e:
            logger.error(f"Error fetching orders for business {business_id}: {str(e)}")
            return []
    
    def update_order(self, order_id: str, update_data: Dict[str, Any]):
        """Update order in database"""
        try:
            order_ref = self.db.collection('orders').document(order_id)
            update_data['updated_at'] = datetime.now()
            order_ref.update(update_data)
            
        except Exception as e:
            logger.error(f"Error updating order {order_id}: {str(e)}")
    
    # Analytics Operations
    def log_whatsapp_event(self, business_id: str, event_type: str, user_id: str, metadata: Dict[str, Any] = None):
        """Log WhatsApp analytics event"""
        try:
            event_data = {
                'business_id': business_id,
                'event_type': event_type,
                'user_id': user_id,
                'metadata': metadata or {},
                'created_at': datetime.now()
            }
            
            self.db.collection('whatsapp_analytics').add(event_data)
            
        except Exception as e:
            logger.error(f"Error logging WhatsApp event for business {business_id}: {str(e)}")
    
    # Utility Operations
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            # Simple test query
            test_ref = self.db.collection('test').limit(1)
            list(test_ref.get())
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {str(e)}")
            return False

# Global database service instance
try:
    database_service = DatabaseService()
except Exception as e:
    logger.error(f"Failed to initialize database service: {str(e)}")
    database_service = None