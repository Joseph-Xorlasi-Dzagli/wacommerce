"""
Business configuration and management models
Handles business-specific configurations, credentials, and settings
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
from cryptography.fernet import Fernet
import base64
import os

from config import logger, BUSINESS_CONFIG_CACHE, BUSINESS_CONFIG_CACHE_UPDATED, BUSINESS_CONFIG_CACHE_DURATION_MINUTES
from services.database import database_service

class BusinessConfig:
    """Business configuration management"""
    
    def __init__(self, business_id: str, business_data: Dict[str, Any], 
                 whatsapp_config: Dict[str, Any], settings: Dict[str, Any] = None):
        self.business_id = business_id
        self.business_data = business_data
        self.whatsapp_config = whatsapp_config
        self.settings = settings or {}
        
        # Extract key WhatsApp credentials
        self.phone_number_id = whatsapp_config.get('phone_number_id')
        self.business_account_id = whatsapp_config.get('business_account_id')
        self.catalog_id = whatsapp_config.get('catalog_id')
        self.verify_token = whatsapp_config.get('verify_token')
        self.webhook_url = whatsapp_config.get('webhook_url')
        
        # Decrypt access token
        self.access_token = self._decrypt_token(whatsapp_config.get('access_token'))
        
        # Build API URL
        self.api_url = f"https://graph.facebook.com/v22.0/{self.phone_number_id}/messages"
        
        # Business status
        self.is_active = business_data.get('is_open', False) and whatsapp_config.get('active', False)
        self.whatsapp_enabled = business_data.get('whatsapp_enabled', False)
    
    def _decrypt_token(self, encrypted_token: str) -> Optional[str]:
        """Decrypt the access token"""
        if not encrypted_token:
            return None
        
        try:
            # Get encryption key from environment
            encryption_key = os.getenv('ENCRYPTION_KEY')
            if not encryption_key:
                logger.warning("No encryption key found, using token as-is")
                return encrypted_token
            
            # Create Fernet instance
            f = Fernet(encryption_key.encode())
            
            # Decrypt token
            decrypted_token = f.decrypt(encrypted_token.encode()).decode()
            return decrypted_token
            
        except Exception as e:
            logger.error(f"Error decrypting access token: {str(e)}")
            # Fallback to using token as-is (for backward compatibility)
            return encrypted_token
    
    def get_greeting_message(self) -> str:
        """Get business-specific greeting message"""
        whatsapp_settings = self.settings.get('whatsapp', {})
        return whatsapp_settings.get('greeting_message', 
                                   f"👋 Welcome to {self.business_data.get('name', 'our store')}! How can I help you today?")
    
    def get_business_hours_message(self) -> str:
        """Get business hours message"""
        whatsapp_settings = self.settings.get('whatsapp', {})
        return whatsapp_settings.get('business_hours_message',
                                   "We're currently closed. Please check back during our business hours.")
    
    def is_auto_reply_enabled(self) -> bool:
        """Check if auto reply is enabled"""
        whatsapp_settings = self.settings.get('whatsapp', {})
        return whatsapp_settings.get('auto_reply_enabled', True)
    
    def is_inventory_check_enabled(self) -> bool:
        """Check if inventory checking is enabled"""
        whatsapp_settings = self.settings.get('whatsapp', {})
        return whatsapp_settings.get('inventory_check_enabled', True)
    
    def get_payment_methods(self) -> List[str]:
        """Get enabled payment methods"""
        checkout_settings = self.settings.get('checkout', {})
        return checkout_settings.get('payment_methods', ['mobile_money', 'cash_on_delivery'])
    
    def get_shipping_methods(self) -> List[str]:
        """Get enabled shipping methods"""
        checkout_settings = self.settings.get('checkout', {})
        return checkout_settings.get('shipping_methods', ['delivery', 'pickup'])
    
    def get_currency(self) -> str:
        """Get business currency"""
        checkout_settings = self.settings.get('checkout', {})
        return checkout_settings.get('currency', 'GHS')
    
    def get_tax_rate(self) -> float:
        """Get business tax rate"""
        checkout_settings = self.settings.get('checkout', {})
        return checkout_settings.get('tax_rate', 0.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for caching"""
        return {
            'business_id': self.business_id,
            'business_data': self.business_data,
            'whatsapp_config': self.whatsapp_config,
            'settings': self.settings,
            'cached_at': datetime.now().isoformat()
        }

class BusinessManager:
    """Business configuration manager with caching"""
    
    @staticmethod
    def get_business_by_phone_id(phone_number_id: str) -> Optional[BusinessConfig]:
        """Get business configuration by phone number ID with caching"""
        
        # Check cache first
        cache_key = f"phone_{phone_number_id}"
        
        if BusinessManager._is_cache_valid(cache_key):
            cached_data = BUSINESS_CONFIG_CACHE.get(cache_key)
            if cached_data:
                logger.debug(f"Returning cached business config for phone ID: {phone_number_id}")
                return BusinessManager._create_business_config_from_cache(cached_data)
        
        # Fetch from database
        if not database_service:
            logger.error("Database service not available")
            return None
        
        try:
            business_data = database_service.get_business_by_phone_id(phone_number_id)
            
            if not business_data:
                logger.warning(f"No business found for phone ID: {phone_number_id}")
                return None
            
            # Get business settings
            business_id = business_data['business_id']
            settings = database_service.get_business_settings(business_id)
            
            # Create business config
            config = BusinessConfig(
                business_id=business_id,
                business_data=business_data['business_data'],
                whatsapp_config=business_data['whatsapp_config'],
                settings=settings
            )
            
            # Validate business configuration
            if not BusinessManager._validate_business_config(config):
                return None
            
            # Cache the result
            BusinessManager._cache_business_config(cache_key, config)
            
            # Update business activity
            database_service.update_business_last_activity(business_id)
            
            logger.info(f"Loaded business config for {config.business_data.get('name', 'Unknown')} (ID: {business_id})")
            return config
            
        except Exception as e:
            logger.error(f"Error getting business by phone ID {phone_number_id}: {str(e)}")
            return None
    
    @staticmethod
    def get_business_by_id(business_id: str) -> Optional[BusinessConfig]:
        """Get business configuration by business ID"""
        
        # Check cache first
        cache_key = f"business_{business_id}"
        
        if BusinessManager._is_cache_valid(cache_key):
            cached_data = BUSINESS_CONFIG_CACHE.get(cache_key)
            if cached_data:
                logger.debug(f"Returning cached business config for business ID: {business_id}")
                return BusinessManager._create_business_config_from_cache(cached_data)
        
        # Fetch from database
        if not database_service:
            logger.error("Database service not available")
            return None
        
        try:
            business_data = database_service.get_business_details(business_id)
            if not business_data:
                return None
            
            # Get WhatsApp config for this business
            # Note: This requires a different query - you'd need to implement this in database_service
            # For now, we'll return None as this method is primarily for caching
            logger.warning(f"Direct business ID lookup not fully implemented: {business_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting business by ID {business_id}: {str(e)}")
            return None
    
    @staticmethod
    def _validate_business_config(config: BusinessConfig) -> bool:
        """Validate business configuration"""
        
        # Check if business is active
        if not config.is_active:
            logger.warning(f"Business {config.business_id} is not active")
            return False
        
        # Check if WhatsApp is enabled
        if not config.whatsapp_enabled:
            logger.warning(f"WhatsApp not enabled for business {config.business_id}")
            return False
        
        # Check required WhatsApp credentials
        required_fields = ['phone_number_id', 'business_account_id', 'access_token']
        for field in required_fields:
            if not getattr(config, field):
                logger.error(f"Missing required field {field} for business {config.business_id}")
                return False
        
        return True
    
    @staticmethod
    def _is_cache_valid(cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in BUSINESS_CONFIG_CACHE_UPDATED:
            return False
        
        cache_time = BUSINESS_CONFIG_CACHE_UPDATED[cache_key]
        cache_age = datetime.now() - cache_time
        
        return cache_age < timedelta(minutes=BUSINESS_CONFIG_CACHE_DURATION_MINUTES)
    
    @staticmethod
    def _cache_business_config(cache_key: str, config: BusinessConfig):
        """Cache business configuration"""
        BUSINESS_CONFIG_CACHE[cache_key] = config.to_dict()
        BUSINESS_CONFIG_CACHE_UPDATED[cache_key] = datetime.now()
        
        logger.debug(f"Cached business config: {cache_key}")
    
    @staticmethod
    def _create_business_config_from_cache(cached_data: Dict[str, Any]) -> BusinessConfig:
        """Create BusinessConfig from cached data"""
        return BusinessConfig(
            business_id=cached_data['business_id'],
            business_data=cached_data['business_data'],
            whatsapp_config=cached_data['whatsapp_config'],
            settings=cached_data['settings']
        )
    
    @staticmethod
    def invalidate_cache(business_id: str = None, phone_number_id: str = None):
        """Invalidate cached business configuration"""
        if business_id:
            cache_key = f"business_{business_id}"
            BUSINESS_CONFIG_CACHE.pop(cache_key, None)
            BUSINESS_CONFIG_CACHE_UPDATED.pop(cache_key, None)
        
        if phone_number_id:
            cache_key = f"phone_{phone_number_id}"
            BUSINESS_CONFIG_CACHE.pop(cache_key, None)
            BUSINESS_CONFIG_CACHE_UPDATED.pop(cache_key, None)
        
        logger.info(f"Invalidated cache for business_id: {business_id}, phone_id: {phone_number_id}")
    
    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'cached_configs': len(BUSINESS_CONFIG_CACHE),
            'cache_keys': list(BUSINESS_CONFIG_CACHE.keys()),
            'oldest_cache': min(BUSINESS_CONFIG_CACHE_UPDATED.values()) if BUSINESS_CONFIG_CACHE_UPDATED else None,
            'newest_cache': max(BUSINESS_CONFIG_CACHE_UPDATED.values()) if BUSINESS_CONFIG_CACHE_UPDATED else None
        }

# Utility functions for encryption (for future use)
def generate_encryption_key() -> str:
    """Generate a new encryption key for tokens"""
    return Fernet.generate_key().decode()

def encrypt_token(token: str, encryption_key: str = None) -> str:
    """Encrypt an access token"""
    if not encryption_key:
        encryption_key = os.getenv('ENCRYPTION_KEY')
        if not encryption_key:
            raise ValueError("No encryption key provided")
    
    f = Fernet(encryption_key.encode())
    encrypted_token = f.encrypt(token.encode()).decode()
    return encrypted_token