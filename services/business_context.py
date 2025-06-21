"""
Business context service for extracting and managing business context from webhooks
Handles business identification, validation, and context switching
"""

from typing import Dict, List, Optional, Any, Tuple
import json
from datetime import datetime

from config import logger, ERROR_MESSAGES
from models.business import BusinessManager, BusinessConfig
from services.database import database_service

class BusinessContextError(Exception):
    """Custom exception for business context errors"""
    pass


class BusinessContext:
    """Container for business context information"""
    
    def __init__(self, config: BusinessConfig, phone_number_id: str, display_phone_number: str = None):
        self.config = config
        self.phone_number_id = phone_number_id
        self.display_phone_number = display_phone_number
        
        # Quick access properties
        self.business_id = config.business_id
        self.business_name = config.business_data.get('name', 'Unknown Business')
        self.access_token = config.access_token
        self.api_url = config.api_url
        self.catalog_id = config.catalog_id
        self.business_account_id = config.business_account_id
        
        # Business settings
        self.currency = config.get_currency()
        self.payment_methods = config.get_payment_methods()
        self.shipping_methods = config.get_shipping_methods()
        
        # Feature flags
        self.inventory_check_enabled = config.is_inventory_check_enabled()
        self.auto_reply_enabled = config.is_auto_reply_enabled()
    
    def get_greeting_message(self) -> str:
        """Get business-specific greeting message"""
        try:
            if hasattr(self.config, 'get_greeting_message'):
                return self.config.get_greeting_message()
            else:
                # Fallback if method doesn't exist
                return f"Welcome to {self.business_name}! How can I help you today?"
        except Exception as e:
            logger.error(f"Error getting greeting message: {str(e)}")
            return "Welcome! How can I help you today?"
    
    def get_business_hours_message(self) -> str:
        """Get business hours message"""
        try:
            if hasattr(self.config, 'get_business_hours_message'):
                return self.config.get_business_hours_message()
            else:
                return "Our business hours are Monday-Friday 9AM-5PM."
        except Exception as e:
            logger.error(f"Error getting business hours message: {str(e)}")
            return "Please contact us during business hours."
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a specific feature is enabled"""
        try:
            feature_map = {
                'inventory_check': self.inventory_check_enabled,
                'auto_reply': self.auto_reply_enabled,
                'whatsapp': getattr(self.config, 'whatsapp_enabled', True)
            }
            return feature_map.get(feature, False)
        except Exception as e:
            logger.error(f"Error checking feature {feature}: {str(e)}")
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/debugging"""
        try:
            return {
                'business_id': self.business_id,
                'business_name': self.business_name,
                'phone_number_id': self.phone_number_id,
                'display_phone_number': self.display_phone_number,
                'catalog_id': self.catalog_id,
                'currency': self.currency,
                'features': {
                    'inventory_check': self.inventory_check_enabled,
                    'auto_reply': self.auto_reply_enabled,
                    'whatsapp': getattr(self.config, 'whatsapp_enabled', True)
                }
            }
        except Exception as e:
            logger.error(f"Error converting business context to dict: {str(e)}")
            return {
                'business_id': getattr(self, 'business_id', 'unknown'),
                'error': str(e)
            }

class BusinessContextService:
    """Service for extracting and managing business context"""
    
    @staticmethod
    def extract_business_context(webhook_data: Dict[str, Any]) -> Optional[BusinessContext]:
        """
        Extract business context from WhatsApp webhook data
        
        Args:
            webhook_data: Complete webhook payload from WhatsApp
            
        Returns:
            BusinessContext object or None if extraction fails
        """
        try:
            # Extract phone number ID from webhook metadata
            phone_number_id = BusinessContextService._extract_phone_number_id(webhook_data)
            
            if not phone_number_id:
                logger.error("No phone number ID found in webhook data")
                return None
            
            # Extract display phone number for logging
            display_phone_number = BusinessContextService._extract_display_phone_number(webhook_data)
            
            # Get business configuration
            business_config = BusinessManager.get_business_by_phone_id(phone_number_id)
            
            if not business_config:
                logger.error(f"No business configuration found for phone ID: {phone_number_id}")
                return None
            
            # Create business context
            context = BusinessContext(
                config=business_config,
                phone_number_id=phone_number_id,
                display_phone_number=display_phone_number
            )
            
            # Log successful context extraction
            logger.info(f"Business context extracted: {context.business_name} (ID: {context.business_id})")
            
            # Log analytics event
            if database_service:
                database_service.log_whatsapp_event(
                    business_id=context.business_id,
                    event_type='webhook_received',
                    user_id='system',
                    metadata={
                        'phone_number_id': phone_number_id,
                        'display_phone_number': display_phone_number
                    }
                )
            
            return context
            
        except Exception as e:
            logger.error(f"Error extracting business context: {str(e)}")
            return None
    
    @staticmethod
    def _extract_phone_number_id(webhook_data: Dict[str, Any]) -> Optional[str]:
        """Extract phone number ID from webhook data"""
        try:
            # Navigate through the webhook structure
            entry = webhook_data.get('entry', [])
            if not entry:
                return None
            
            for entry_item in entry:
                changes = entry_item.get('changes', [])
                for change in changes:
                    if change.get('field') == 'messages':
                        value = change.get('value', {})
                        metadata = value.get('metadata', {})
                        phone_number_id = metadata.get('phone_number_id')
                        
                        if phone_number_id:
                            return phone_number_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting phone number ID: {str(e)}")
            return None
    
    @staticmethod
    def _extract_display_phone_number(webhook_data: Dict[str, Any]) -> Optional[str]:
        """Extract display phone number from webhook data"""
        try:
            entry = webhook_data.get('entry', [])
            if not entry:
                return None
            
            for entry_item in entry:
                changes = entry_item.get('changes', [])
                for change in changes:
                    if change.get('field') == 'messages':
                        value = change.get('value', {})
                        metadata = value.get('metadata', {})
                        display_phone_number = metadata.get('display_phone_number')
                        
                        if display_phone_number:
                            return display_phone_number
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting display phone number: {str(e)}")
            return None
    
    @staticmethod
    def validate_business_context(context: BusinessContext) -> Tuple[bool, str]:
        """
        Validate business context for processing
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check if business is active
            if not context.config.is_active:
                return False, ERROR_MESSAGES.get('business_inactive', 'Business is inactive')
            
            # Check if WhatsApp is enabled
            if not context.config.whatsapp_enabled:
                return False, ERROR_MESSAGES.get('whatsapp_not_enabled', 'WhatsApp not enabled')
            
            # Check required credentials
            if not context.access_token:
                return False, ERROR_MESSAGES.get('configuration_error', 'Missing access token')
            
            if not context.catalog_id:
                logger.warning(f"No catalog ID for business {context.business_id}")
                # Don't fail - some features might work without catalog
            
            return True, "Valid"
            
        except Exception as e:
            logger.error(f"Error validating business context: {str(e)}")
            return False, ERROR_MESSAGES.get('configuration_error', 'Configuration error')
    
    @staticmethod
    def get_business_context_summary(context: BusinessContext) -> Dict[str, Any]:
        """Get a summary of business context for logging"""
        return {
            'business_id': context.business_id,
            'business_name': context.business_name,
            'phone_number_id': context.phone_number_id,
            'display_phone_number': context.display_phone_number,
            'has_catalog': bool(context.catalog_id),
            'currency': context.currency,
            'active_features': [
                feature for feature in ['inventory_check', 'auto_reply', 'whatsapp']
                if context.is_feature_enabled(feature)
            ]
        }
    
    @staticmethod
    def handle_business_context_error(error_type: str, user_id: str = None) -> Dict[str, Any]:
        """
        Handle business context errors and return appropriate response
        
        Returns:
            Dictionary with error response for the user
        """
        error_message = ERROR_MESSAGES.get(error_type, 'An error occurred. Please try again.')
        
        response = {
            'error': True,
            'error_type': error_type,
            'message': error_message,
            'timestamp': datetime.now().isoformat()
        }
        
        if user_id:
            response['user_id'] = user_id
        
        logger.error(f"Business context error: {error_type} - {error_message}")
        
        return response

# Context manager for business operations
class BusinessContextManager:
    """Context manager for business-scoped operations"""
    
    def __init__(self, business_context: BusinessContext):
        self.business_context = business_context
        self.original_env = {}
    
    def __enter__(self):
        """Set up business context environment"""
        # Could be used to temporarily set environment variables
        # or configure global state for business operations
        return self.business_context
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up business context environment"""
        # Restore original environment if needed
        pass

# Utility functions
def get_business_scoped_cache_key(business_id: str, base_key: str) -> str:
    """Generate business-scoped cache key"""
    return f"{business_id}:{base_key}"

def get_business_scoped_session_id(business_id: str, user_id: str) -> str:
    """Generate business-scoped session ID"""
    return f"{business_id}_{user_id}"