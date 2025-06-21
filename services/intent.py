import json
import re
from config import OPENAI_API_KEY, OPENAI_MODEL, logger
from models.session import get_recent_history
from utils.logger import get_logger

logger = get_logger(__name__)

# Initialize OpenAI client with error handling
try:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {str(e)}")
    # Fallback initialization or alternative approach
    try:
        import openai
        openai.api_key = OPENAI_API_KEY
        client = None  # Will use legacy openai module instead
    except ImportError:
        logger.error("OpenAI library not available")
        client = None

def process_intent(user_message, business_id, user_id):
    """Analyze user message to determine intent using OpenAI API with business context"""
    # Get recent conversation history with business context
    conversation_history = get_recent_history(business_id, user_id, limit=5)
    
    logger.info(f"Processing intent for business {business_id}, user {user_id}: {user_message}")
    
    # Prepare conversation history for context
    conversation = []
    for message in conversation_history:
        conversation.append({"role": message["role"], "content": message["content"]})
    
    # Add current message
    conversation.append({"role": "user", "content": user_message})
    
    # Business-aware prompt - could be customized per business in the future
    system_prompt = """You are an e-commerce assistant for a WhatsApp store. 
    Determine the user's intent from the following categories:
    - greeting: User is saying hello or starting conversation
    - browse_catalog: User wants to see products or categories
    - browse_product: User is looking for a specific product or product type
    - product_info: User is asking about specific product details
    - add_to_cart: User wants to add item(s) to cart
    - view_cart: User wants to see what's in their cart
    - checkout: User wants to complete their purchase
    - order_status: User is asking about an existing order
    - support: User needs help or has questions
    - feedback: User is providing feedback
    - cancel: User wants to cancel or reset their current action
    
    Respond with ONLY the intent category and any relevant entities (like product names, quantities).
    Format: {"intent": "category", "entities": {"product": "name", "quantity": number}}"""
    
    try:
        if client:  # Use new OpenAI client
            prompt = [
                {"role": "system", "content": system_prompt},
                *conversation
            ]
            
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=prompt,
                temperature=0.3,
                max_tokens=150
            )
            
            intent_text = response.choices[0].message.content.strip()
        else:  # Fallback to legacy openai module
            import openai
            
            prompt = [
                {"role": "system", "content": system_prompt},
                *conversation
            ]
            
            response = openai.ChatCompletion.create(
                model=OPENAI_MODEL,
                messages=prompt,
                temperature=0.3,
                max_tokens=150
            )
            
            intent_text = response.choices[0].message.content.strip()
        
        logger.debug(f"Intent text from OpenAI for business {business_id}: {intent_text}")
        
        # Try to parse the intent as JSON
        try:
            intent_data = json.loads(intent_text)
            logger.info(f"Parsed intent for business {business_id}: {intent_data}")
            
            # Log analytics event for intent recognition
            log_intent_analytics(business_id, user_id, intent_data, user_message)
            
            return intent_data
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse intent as JSON for business {business_id}: {intent_text}")
            
            # Fallback to pattern matching with business context
            fallback_intent = analyze_message_content_with_business(user_message, business_id)
            
            # Log fallback usage
            _log_database_event(
                business_id, user_id, 'intent_fallback',
                {
                    'intent': fallback_intent.get('intent', 'unknown'),
                    'fallback_reason': 'json_parse_error',
                    'original_response': intent_text
                }
            )
            
            return fallback_intent
                
    except Exception as e:
        logger.error(f"Error processing intent for business {business_id}: {str(e)}")
        
        # Fallback to pattern matching
        fallback_intent = analyze_message_content_with_business(user_message, business_id)
        
        # Log error
        _log_database_event(
            business_id, user_id, 'intent_error',
            {
                'error': str(e),
                'fallback_intent': fallback_intent.get('intent', 'unknown'),
                'message': user_message
            }
        )
        
        return fallback_intent

def analyze_message_content_with_business(message, business_id=None):
    """Perform simple text analysis on a message with optional business context"""
    message = message.lower()
    
    # Check for common patterns in the message
    if re.search(r'\b(hi|hello|hey|greetings|good morning|good afternoon|good evening)\b', message):
        return {"intent": "greeting"}
    
    if re.search(r'\b(show|browse|see|explore|catalog|products|categories|menu)\b', message):
        return {"intent": "browse_catalog"}
    
    if re.search(r'\b(looking\s+for|find|search|do\s+you\s+have|need|want)\b', message):
        # Try to extract product
        product_match = re.search(r'(looking\s+for|find|search|have|need|want)\s+(?:a|an|some|the)?\s+([^\?\.]+)', message)
        if product_match:
            product = product_match.group(2).strip()
            return {"intent": "browse_product", "entities": {"product": product}}
        return {"intent": "browse_product"}
    
    if re.search(r'\b(add|put)\b.+\b(cart|basket)\b', message):
        # Try to extract quantity
        quantity_match = re.search(r'\b(\d+)\b', message)
        quantity = int(quantity_match.group(1)) if quantity_match else 1
        return {"intent": "add_to_cart", "entities": {"quantity": quantity}}
    
    if re.search(r'\b(cart|basket|shopping\s+cart|my\s+cart)\b', message) and not re.search(r'\b(add|put)\b', message):
        return {"intent": "view_cart"}
    
    if re.search(r'\b(checkout|pay|purchase|buy|order\s+now|proceed|complete)\b', message):
        return {"intent": "checkout"}
    
    if re.search(r'\b(order|orders|status|tracking|track|delivery)\b', message):
        return {"intent": "order_status"}
    
    if re.search(r'\b(help|support|question|problem|issue|assist|contact|faq)\b', message):
        return {"intent": "support"}
    
    if re.search(r'\b(feedback|review|rating|complain|suggest)\b', message):
        return {"intent": "feedback"}
    
    if re.search(r'\b(cancel|stop|reset|clear|abort|quit)\b', message):
        return {"intent": "cancel"}
    
    # Business-specific patterns could be added here based on business_id
    # For example, specific product categories, brand names, etc.
    
    # Default to unknown intent
    return {"intent": "unknown"}

def get_product_from_intent(intent_data):
    """Extract product information from intent data"""
    if not intent_data or "entities" not in intent_data:
        return None
    
    entities = intent_data["entities"]
    if "product" in entities:
        return entities["product"]
    
    return None

def get_quantity_from_intent(intent_data, default=1):
    """Extract quantity information from intent data"""
    if not intent_data or "entities" not in intent_data:
        return default
    
    entities = intent_data["entities"]
    if "quantity" in entities:
        try:
            quantity = int(entities["quantity"])
            return max(1, quantity)  # Ensure quantity is at least 1
        except (ValueError, TypeError):
            return default
    
    return default

def get_category_from_intent(intent_data):
    """Extract category information from intent data"""
    if not intent_data or "entities" not in intent_data:
        return None
    
    entities = intent_data["entities"]
    if "category" in entities:
        return entities["category"]
    
    return None

def get_order_id_from_intent(intent_data):
    """Extract order ID from intent data"""
    if not intent_data or "entities" not in intent_data:
        return None
    
    entities = intent_data["entities"]
    if "order_id" in entities:
        return entities["order_id"]
    
    return None

def enhance_intent_with_business_context(intent_data, business_context):
    """Enhance intent data with business-specific context"""
    if not intent_data or not business_context:
        return intent_data
    
    # Add business-specific enhancements
    enhanced_intent = intent_data.copy()
    
    # Add business context metadata
    enhanced_intent["business_context"] = {
        "business_id": business_context.business_id,
        "business_name": business_context.business_name,
        "currency": business_context.currency,
        "features": {
            "inventory_check": business_context.inventory_check_enabled,
            "auto_reply": business_context.auto_reply_enabled
        }
    }
    
    # Business-specific intent modifications could go here
    # For example, mapping product names to business-specific variants
    
    return enhanced_intent

def get_intent_confidence_score(intent_data, message):
    """Calculate a confidence score for the intent recognition"""
    if not intent_data:
        return 0.0
    
    intent = intent_data.get("intent", "unknown")
    
    # Simple confidence scoring based on pattern matching
    message_lower = message.lower()
    
    confidence_scores = {
        "greeting": 0.9 if re.search(r'\b(hi|hello|hey)\b', message_lower) else 0.5,
        "browse_catalog": 0.8 if re.search(r'\b(browse|catalog|menu)\b', message_lower) else 0.6,
        "browse_product": 0.8 if re.search(r'\b(looking for|find|search)\b', message_lower) else 0.6,
        "add_to_cart": 0.9 if re.search(r'\b(add.*cart|put.*cart)\b', message_lower) else 0.5,
        "view_cart": 0.9 if re.search(r'\b(my cart|view cart)\b', message_lower) else 0.7,
        "checkout": 0.9 if re.search(r'\b(checkout|pay now)\b', message_lower) else 0.6,
        "order_status": 0.8 if re.search(r'\b(order status|track)\b', message_lower) else 0.6,
        "support": 0.8 if re.search(r'\b(help|support)\b', message_lower) else 0.6,
        "feedback": 0.7 if re.search(r'\b(feedback|review)\b', message_lower) else 0.5,
        "cancel": 0.9 if re.search(r'\b(cancel|stop)\b', message_lower) else 0.5,
        "unknown": 0.1
    }
    
    return confidence_scores.get(intent, 0.5)

def log_intent_analytics(business_id, user_id, intent_data, message, confidence_score=None):
    """Log intent recognition analytics"""
    try:
        metadata = {
            'intent': intent_data.get('intent', 'unknown'),
            'entities': intent_data.get('entities', {}),
            'message_length': len(message),
            'confidence_score': confidence_score or get_intent_confidence_score(intent_data, message),
            'has_entities': bool(intent_data.get('entities')),
            'entity_count': len(intent_data.get('entities', {}))
        }
        
        _log_database_event(business_id, user_id, 'intent_processed', metadata)
        
    except Exception as e:
        logger.error(f"Error logging intent analytics: {str(e)}")

def _log_database_event(business_id, user_id, event_type, metadata):
    """Helper function to log database events"""
    try:
        from services.database import database_service
        if database_service:
            database_service.log_whatsapp_event(
                business_id=business_id,
                event_type=event_type,
                user_id=user_id,
                metadata=metadata
            )
    except Exception as e:
        logger.error(f"Error logging database event: {str(e)}")

# Legacy functions for backward compatibility
def process_intent_legacy(user_message, user_id):
    """Legacy function - use process_intent with business_id instead"""
    logger.warning("Using deprecated process_intent_legacy function")
    from config import BUSINESS_ID
    return process_intent(user_message, BUSINESS_ID or "default_business", user_id)

def analyze_message_content(message):
    """Legacy function - use analyze_message_content_with_business instead"""
    logger.warning("Using deprecated analyze_message_content function")
    return analyze_message_content_with_business(message)

def parse_intent_fallback(intent_text):
    """Parse intent when JSON parsing fails - legacy compatibility"""
    logger.warning("Using deprecated parse_intent_fallback function")
    intent_text_lower = intent_text.lower()
    
    if "greeting" in intent_text_lower:
        return {"intent": "greeting"}
    elif "browse_product" in intent_text_lower:
        # Extract product name if possible
        product_match = re.search(r"product[\"\':\s]+([^\"\'\}\,]+)", intent_text)
        if product_match:
            return {"intent": "browse_product", "entities": {"product": product_match.group(1)}}
        return {"intent": "browse_product"}
    elif "browse" in intent_text_lower or "catalog" in intent_text_lower:
        return {"intent": "browse_catalog"}
    elif "cart" in intent_text_lower and "add" in intent_text_lower:
        return {"intent": "add_to_cart"}
    elif "cart" in intent_text_lower or "basket" in intent_text_lower:
        return {"intent": "view_cart"}
    elif "checkout" in intent_text_lower or "pay" in intent_text_lower:
        return {"intent": "checkout"}
    elif "order" in intent_text_lower and "status" in intent_text_lower:
        return {"intent": "order_status"}
    elif "help" in intent_text_lower or "support" in intent_text_lower:
        return {"intent": "support"}
    else:
        return {"intent": "unknown"}