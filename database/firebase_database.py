import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import json
import os
from utils.logger import get_logger

logger = get_logger(__name__)

class FirebaseDatabase:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirebaseDatabase, cls).__new__(cls)
            cls._instance.db = None
            cls._instance.initialized = False
        return cls._instance
    
    def initialize(self, credentials_path=None, project_id=None):
        """Initialize Firebase connection"""
        if self.initialized:
            return True
        
        try:
            # Initialize Firebase Admin SDK
            if credentials_path and os.path.exists(credentials_path):
                cred = credentials.Certificate(credentials_path)
                firebase_admin.initialize_app(cred, {
                    'projectId': project_id
                })
            else:
                # Use default credentials (e.g., from environment)
                firebase_admin.initialize_app()
            
            # Initialize Firestore client
            self.db = firestore.client()
            self.initialized = True
            
            logger.info("Firebase Database initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            self.initialized = False
            return False
    
    def is_connected(self):
        """Check if Firebase is connected"""
        return self.initialized and self.db is not None
    
    def get_collection(self, collection_name):
        """Get a reference to a collection"""
        if not self.is_connected():
            logger.error("Firebase not connected")
            return None
        return self.db.collection(collection_name)
    
    def add_document(self, collection_name, data):
        """Add a document to a collection"""
        try:
            if not self.is_connected():
                logger.error("Firebase not connected")
                return None
            
            # Add server timestamp if not present
            if 'created_at' not in data:
                data['created_at'] = firestore.SERVER_TIMESTAMP
            if 'updated_at' not in data:
                data['updated_at'] = firestore.SERVER_TIMESTAMP
            
            doc_ref = self.db.collection(collection_name).add(data)
            logger.info(f"Document added to {collection_name} with ID: {doc_ref[1].id}")
            return doc_ref[1].id
            
        except Exception as e:
            logger.error(f"Error adding document to {collection_name}: {str(e)}")
            return None
    
    def get_document(self, collection_name, document_id):
        """Get a document by ID"""
        try:
            if not self.is_connected():
                logger.error("Firebase not connected")
                return None
            
            doc_ref = self.db.collection(collection_name).document(document_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting document {document_id} from {collection_name}: {str(e)}")
            return None
    
    def update_document(self, collection_name, document_id, data):
        """Update a document"""
        try:
            if not self.is_connected():
                logger.error("Firebase not connected")
                return False
            
            # Add update timestamp
            data['updated_at'] = firestore.SERVER_TIMESTAMP
            
            doc_ref = self.db.collection(collection_name).document(document_id)
            doc_ref.update(data)
            
            logger.info(f"Document {document_id} updated in {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating document {document_id} in {collection_name}: {str(e)}")
            return False
    
    def delete_document(self, collection_name, document_id):
        """Delete a document"""
        try:
            if not self.is_connected():
                logger.error("Firebase not connected")
                return False
            
            doc_ref = self.db.collection(collection_name).document(document_id)
            doc_ref.delete()
            
            logger.info(f"Document {document_id} deleted from {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting document {document_id} from {collection_name}: {str(e)}")
            return False
    
    def query_documents(self, collection_name, field, operator, value, limit=None, order_by=None, direction='asc'):
        """Query documents in a collection"""
        try:
            if not self.is_connected():
                logger.error("Firebase not connected")
                return []
            
            query = self.db.collection(collection_name).where(field, operator, value)
            
            if order_by:
                if direction.lower() == 'desc':
                    query = query.order_by(order_by, direction=firestore.Query.DESCENDING)
                else:
                    query = query.order_by(order_by)
            
            if limit:
                query = query.limit(limit)
            
            results = []
            for doc in query.stream():
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)
            
            return results
            
        except Exception as e:
            logger.error(f"Error querying {collection_name}: {str(e)}")
            return []
    
    def log_analytics_event(self, event_type, user_id, metadata=None):
        """Log an analytics event"""
        try:
            analytics_data = {
                'event_type': event_type,
                'user_id': user_id,
                'metadata': metadata or {},
                'created_at': firestore.SERVER_TIMESTAMP
            }
            
            self.add_document('whatsapp_analytics', analytics_data)
            logger.debug(f"Analytics event logged: {event_type} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error logging analytics event: {str(e)}")
    
    def get_user_session(self, session_id):
        """Get WhatsApp session data"""
        try:
            return self.get_document('whatsapp_sessions', session_id)
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {str(e)}")
            return None
    
    def save_user_session(self, session_id, session_data):
        """Save WhatsApp session data"""
        try:
            # Check if session exists
            existing_session = self.get_user_session(session_id)
            
            if existing_session:
                return self.update_document('whatsapp_sessions', session_id, session_data)
            else:
                # Create new session with the session_id as document ID
                session_data['created_at'] = firestore.SERVER_TIMESTAMP
                session_data['updated_at'] = firestore.SERVER_TIMESTAMP
                
                doc_ref = self.db.collection('whatsapp_sessions').document(session_id)
                doc_ref.set(session_data)
                return True
                
        except Exception as e:
            logger.error(f"Error saving session {session_id}: {str(e)}")
            return False
    
    def get_customer_by_whatsapp(self, whatsapp_number):
        """Get customer by WhatsApp number"""
        try:
            customers = self.query_documents(
                'customers', 
                'whatsapp_number', 
                '==', 
                whatsapp_number,
                limit=1
            )
            return customers[0] if customers else None
            
        except Exception as e:
            logger.error(f"Error getting customer by WhatsApp {whatsapp_number}: {str(e)}")
            return None
    
    def create_customer(self, customer_data):
        """Create a new customer"""
        try:
            return self.add_document('customers', customer_data)
        except Exception as e:
            logger.error(f"Error creating customer: {str(e)}")
            return None
    
    def get_customer_addresses(self, customer_id):
        """Get customer's saved addresses"""
        try:
            return self.query_documents(
                'customer_addresses',
                'customer_id',
                '==',
                customer_id,
                order_by='last_used',
                direction='desc'
            )
        except Exception as e:
            logger.error(f"Error getting addresses for customer {customer_id}: {str(e)}")
            return []
    
    def save_customer_address(self, address_data):
        """Save customer address"""
        try:
            return self.add_document('customer_addresses', address_data)
        except Exception as e:
            logger.error(f"Error saving customer address: {str(e)}")
            return None
    
    def get_customer_payment_accounts(self, customer_id):
        """Get customer's payment accounts"""
        try:
            return self.query_documents(
                'payment_accounts',
                'customer_id',
                '==',
                customer_id,
                order_by='last_used',
                direction='desc'
            )
        except Exception as e:
            logger.error(f"Error getting payment accounts for customer {customer_id}: {str(e)}")
            return []
    
    def save_payment_account(self, account_data):
        """Save customer payment account"""
        try:
            return self.add_document('payment_accounts', account_data)
        except Exception as e:
            logger.error(f"Error saving payment account: {str(e)}")
            return None
    
    def create_order(self, order_data):
        """Create a new order"""
        try:
            return self.add_document('orders', order_data)
        except Exception as e:
            logger.error(f"Error creating order: {str(e)}")
            return None
    
    def get_order(self, order_id):
        """Get order by ID"""
        try:
            return self.get_document('orders', order_id)
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {str(e)}")
            return None
    
    def update_order(self, order_id, order_data):
        """Update order"""
        try:
            return self.update_document('orders', order_id, order_data)
        except Exception as e:
            logger.error(f"Error updating order {order_id}: {str(e)}")
            return False
    
    def get_customer_orders(self, customer_id):
        """Get orders for a customer"""
        try:
            return self.query_documents(
                'orders',
                'customer.id',
                '==',
                customer_id,
                order_by='created_at',
                direction='desc'
            )
        except Exception as e:
            logger.error(f"Error getting orders for customer {customer_id}: {str(e)}")
            return []
    
    def save_order_item(self, order_id, item_data):
        """Save order item as subcollection"""
        try:
            if not self.is_connected():
                return None
            
            item_data['created_at'] = firestore.SERVER_TIMESTAMP
            
            # Add to subcollection
            doc_ref = self.db.collection('orders').document(order_id).collection('items').add(item_data)
            return doc_ref[1].id
            
        except Exception as e:
            logger.error(f"Error saving order item for order {order_id}: {str(e)}")
            return None
    
    def get_order_items(self, order_id):
        """Get items for an order"""
        try:
            if not self.is_connected():
                return []
            
            items = []
            items_ref = self.db.collection('orders').document(order_id).collection('items')
            
            for doc in items_ref.stream():
                item_data = doc.to_dict()
                item_data['id'] = doc.id
                items.append(item_data)
            
            return items
            
        except Exception as e:
            logger.error(f"Error getting items for order {order_id}: {str(e)}")
            return []
    
    def log_order_history(self, order_id, status, notes="", created_by="system"):
        """Log order status change"""
        try:
            history_data = {
                'order_id': order_id,
                'status': status,
                'notes': notes,
                'created_by': created_by,
                'notification_sent': False,
                'created_at': firestore.SERVER_TIMESTAMP
            }
            
            return self.add_document('order_history', history_data)
            
        except Exception as e:
            logger.error(f"Error logging order history for {order_id}: {str(e)}")
            return None
    
    def save_inventory_data(self, product_id, inventory_data):
        """Save inventory information"""
        try:
            # Check if inventory record exists
            existing = self.query_documents(
                'inventory',
                'product_id',
                '==',
                product_id,
                limit=1
            )
            
            if existing:
                return self.update_document('inventory', existing[0]['id'], inventory_data)
            else:
                inventory_data['product_id'] = product_id
                return self.add_document('inventory', inventory_data)
                
        except Exception as e:
            logger.error(f"Error saving inventory for product {product_id}: {str(e)}")
            return False
    
    def get_inventory_data(self, product_id):
        """Get inventory data for a product"""
        try:
            inventory = self.query_documents(
                'inventory',
                'product_id',
                '==',
                product_id,
                limit=1
            )
            return inventory[0] if inventory else None
            
        except Exception as e:
            logger.error(f"Error getting inventory for product {product_id}: {str(e)}")
            return None
    
    def batch_write(self, operations):
        """Perform batch write operations"""
        try:
            if not self.is_connected():
                return False
            
            batch = self.db.batch()
            
            for operation in operations:
                op_type = operation.get('type')
                collection = operation.get('collection')
                doc_id = operation.get('document_id')
                data = operation.get('data', {})
                
                if op_type == 'set':
                    doc_ref = self.db.collection(collection).document(doc_id)
                    batch.set(doc_ref, data)
                elif op_type == 'update':
                    doc_ref = self.db.collection(collection).document(doc_id)
                    batch.update(doc_ref, data)
                elif op_type == 'delete':
                    doc_ref = self.db.collection(collection).document(doc_id)
                    batch.delete(doc_ref)
            
            batch.commit()
            logger.info(f"Batch write completed with {len(operations)} operations")
            return True
            
        except Exception as e:
            logger.error(f"Error in batch write: {str(e)}")
            return False
    
    @property
    def SERVER_TIMESTAMP(self):
        """Get server timestamp"""
        return firestore.SERVER_TIMESTAMP
    
    @property
    def FieldValue(self):
        """Get FieldValue for operations like increment"""
        return firestore.FieldValue
    
    @property
    def GeoPoint(self):
        """Get GeoPoint for geographic coordinates"""
        return firestore.GeoPoint

# Global instance
firebase_db = FirebaseDatabase()

def initialize_firebase(credentials_path=None, project_id=None):
    """Initialize Firebase with credentials"""
    return firebase_db.initialize(credentials_path, project_id)