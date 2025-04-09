import json
import re
import openai
from config import OPENAI_API_KEY, OPENAI_MODEL
from models.session import init_user_session, get_recent_history
from utils.logger import get_logger

logger = get_logger(__name__)

# Initialize OpenAI client
openai.api_key = OPENAI_API_KEY

def process_intent(user_message, user_id):
    """Analyze user message to determine intent using OpenAI API"""
    # Get recent conversation history
    conversation_history = get_recent_history(user_id, limit=5)
    
    logger.info(f"ChatGPT User message: {user_message}")
    # Prepare conversation history for context
    conversation = []
    for message in conversation_history:
        conversation.append({"role": message["role"], "content": message["content"]})
    
    # Add current message
    conversation.append({"role": "user", "content": user_message})
    
    prompt = [
        {"role": "system", "content": """You are an e-commerce assistant for a WhatsApp store. 
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
        Format: {{"intent": "category", "entities": {{"product": "name", "quantity": number}}}}"""},
        *conversation
    ]
    
    try:
        response = openai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=prompt,
            temperature=0.3,
            max_tokens=150
        )
        
        intent_text = response.choices[0].message.content.strip()
        logger.debug(f"Intent text from OpenAI: {intent_text}")
        
        # Try to parse the intent as JSON
        try:
            intent_data = json.loads(intent_text)
            logger.info(f"Parsed intent: {intent_data}")
            return intent_data
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse intent as JSON: {intent_text}")
            # If not valid JSON, extract intent manually
            if "greeting" in intent_text.lower():
                return {"intent": "greeting"}
            elif "browse_product" in intent_text.lower():
                # Extract product name if possible
                product_match = re.search(r"product[\"\':\s]+([^\"\'\}\,]+)", intent_text)
                if product_match:
                    return {"intent": "browse_product", "entities": {"product": product_match.group(1)}}
                return {"intent": "browse_product"}
            elif "browse" in intent_text.lower() or "catalog" in intent_text.lower():
                return {"intent": "browse_catalog"}
            elif "cart" in intent_text.lower() and "add" in intent_text.lower():
                return {"intent": "add_to_cart"}
            elif "cart" in intent_text.lower() or "basket" in intent_text.lower():
                return {"intent": "view_cart"}
            elif "checkout" in intent_text.lower() or "pay" in intent_text.lower():
                return {"intent": "checkout"}
            elif "order" in intent_text.lower() and "status" in intent_text.lower():
                return {"intent": "order_status"}
            elif "help" in intent_text.lower() or "support" in intent_text.lower():
                return {"intent": "support"}
            else:
                return {"intent": "unknown"}
                
    except Exception as e:
        logger.error(f"Error processing intent: {str(e)}")
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

def analyze_message_content(message):
    """Perform simple text analysis on a message without using OpenAI"""
    message = message.lower()
    
    # Check for common patterns in the message
    if re.search(r'\b(hi|hello|hey|greetings)\b', message):
        return {"intent": "greeting"}
    
    if re.search(r'\b(show|browse|see|explore|catalog|products|categories)\b', message):
        return {"intent": "browse_catalog"}
    
    if re.search(r'\b(looking\s+for|find|search|do\s+you\s+have)\b', message):
        # Try to extract product
        product_match = re.search(r'(looking\s+for|find|search|have)\s+(?:a|an|some|the)?\s+([^\?\.]+)', message)
        if product_match:
            product = product_match.group(2).strip()
            return {"intent": "browse_product", "entities": {"product": product}}
        return {"intent": "browse_product"}
    
    if re.search(r'\b(add|put)\b.+\b(cart|basket)\b', message):
        return {"intent": "add_to_cart"}
    
    if re.search(r'\b(cart|basket|shopping\s+cart)\b', message):
        return {"intent": "view_cart"}
    
    if re.search(r'\b(checkout|pay|purchase|buy|order\s+now)\b', message):
        return {"intent": "checkout"}
    
    if re.search(r'\b(order|orders|status|tracking)\b', message):
        return {"intent": "order_status"}
    
    if re.search(r'\b(help|support|question|problem|issue|assist)\b', message):
        return {"intent": "support"}
    
    if re.search(r'\b(cancel|stop|reset|clear)\b', message):
        return {"intent": "cancel"}
    
    # Default to unknown intent
    return {"intent": "unknown"}