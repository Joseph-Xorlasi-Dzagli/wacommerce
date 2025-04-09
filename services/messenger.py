import requests
from config import WHATSAPP_API_URL, WHATSAPP_TOKEN
from utils.logger import get_logger

logger = get_logger(__name__)

def send_whatsapp_message(recipient_id, message_data):
    """Base function to send any type of WhatsApp message"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {WHATSAPP_TOKEN}"
    }
    
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_id,
        **message_data
    }
    
    try:
        response = requests.post(WHATSAPP_API_URL, headers=headers, json=data)
        
        if response.status_code != 200:
            logger.error(f"Failed to send message: {response.text}")
            return None
        
        return response.json()
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {str(e)}")
        return None

def send_text_message(recipient_id, text):
    """Send a simple text message"""
    message_data = {
        "type": "text",
        "text": {"body": text}
    }
    return send_whatsapp_message(recipient_id, message_data)

def send_button_message(recipient_id, header_text, body_text, buttons):
    """Send an interactive message with buttons"""
    message_data = {
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {
                "type": "text",
                "text": header_text
            },
            "body": {
                "text": body_text
            },
            "action": {
                "buttons": buttons
            }
        }
    }
    return send_whatsapp_message(recipient_id, message_data)


def send_location_request_message(recipient_id, body_text):
    """Send an interactive location request message to get user's location"""
    message_data = {
        "type": "interactive",
        "interactive": {
            "type": "location_request_message",
            "body": {
                "text": body_text
            },
            "action": {
                "name": "send_location"
            }
        }
    }
    return send_whatsapp_message(recipient_id, message_data)

def send_list_message(recipient_id, header_text, body_text, button_text, sections):
    """Send an interactive message with a list of options"""
    message_data = {
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {
                "type": "text",
                "text": header_text
            },
            "body": {
                "text": body_text
            },
            "action": {
                "button": button_text,
                "sections": sections
            }
        }
    }
    return send_whatsapp_message(recipient_id, message_data)

def send_media_card_carousel(recipient_id, customer_name, discount_percent, promo_code, cards):
    """Send a media card carousel with product images and buttons"""
    # Prepare cards for the template
    template_cards = []
    
    for idx, card in enumerate(cards):
        card_data = {
            "card_index": idx,
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "image",
                            "image": {
                                "id": card["image_id"]
                            }
                        }
                    ]
                },
                {
                    "type": "button",
                    "sub_type": "quick_reply",
                    "index": "0",
                    "parameters": [
                        {
                            "type": "payload",
                            "payload": card["quick_reply_payload"]
                        }
                    ]
                },
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": "1",
                    "parameters": [
                        {
                            "type": "text",
                            "text": card["url_button_text"]
                        }
                    ]
                }
            ]
        }
        template_cards.append(card_data)
    
    # Create the message data
    message_data = {
        "type": "template",
        "template": {
            "name": "carousel_template_media_cards_v1",
            "language": {
                "code": "en_US"
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": customer_name
                        },
                        {
                            "type": "text",
                            "text": discount_percent
                        },
                        {
                            "type": "text",
                            "text": promo_code
                        }
                    ]
                },
                {
                    "type": "carousel",
                    "cards": template_cards
                }
            ]
        }
    }
    
    return send_whatsapp_message(recipient_id, message_data)

def send_product_card_carousel(recipient_id, products, header_text="Featured Products", recipient_name="Customer"):
    """Send a product carousel using WhatsApp product templates"""
    from config import CATALOG_ID
    
    if not products or len(products) == 0:
        logger.error("No products provided for carousel")
        return None
    
    # Limit to max 10 products as per WhatsApp limitation
    products = products[:10]
    
    # Create cards for the carousel
    cards = []
    for i, product in enumerate(products):
        if i >= 10:  # WhatsApp maximum limit
            break
            
        card = {
            "card_index": i,
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "product",
                            "product": {
                                "product_retailer_id": product.get("retailer_id", product.get("id", "")),
                                "catalog_id": product.get("catalog_id", CATALOG_ID)
                            }
                        }
                    ]
                }
            ]
        }
        cards.append(card)
    
    # Create the message data
    message_data = {
        "type": "template",
        "template": {
            "name": "carousel_template_product_cards_v1",
            "language": {
                "code": "en_US"
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": recipient_name
                        }
                    ]
                },
                {
                    "type": "carousel",
                    "cards": cards
                }
            ]
        }
    }
    
    return send_whatsapp_message(recipient_id, message_data)

def send_rich_product_carousel(recipient_id, products):
    """Send a rich interactive product carousel"""
    from config import CATALOG_ID
    
    if not products or len(products) == 0:
        logger.error("No products provided for carousel")
        return None
    
    # Limit to 10 products max
    products = products[:10]
    
    # Create interactive carousel with product cards
    message_data = {
        "type": "interactive",
        "interactive": {
            "type": "product_carousel",
            "action": {
                "catalog_id": CATALOG_ID,
                "products": [{"id": product["id"]} for product in products]
            }
        }
    }
    
    # Send the message
    return send_whatsapp_message(recipient_id, message_data)

def send_location_request(recipient_id, text="Please share your location for delivery"):
    """Request the user's location"""
    message_data = {
        "type": "text",
        "text": {"body": text}
    }
    return send_whatsapp_message(recipient_id, message_data)

def send_image_message(recipient_id, image_url=None, image_id=None, caption=None):
    """Send an image message"""
    message_data = {
        "type": "image"
    }
    
    if image_url:
        message_data["image"] = {"link": image_url}
    elif image_id:
        message_data["image"] = {"id": image_id}
    else:
        logger.error("Either image_url or image_id must be provided")
        return None
    
    if caption:
        message_data["image"]["caption"] = caption
    
    return send_whatsapp_message(recipient_id, message_data)

def send_template_message(recipient_id, template_name, language_code="en_US", components=None):
    """Send a template message"""
    message_data = {
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code
            }
        }
    }
    
    if components:
        message_data["template"]["components"] = components
    
    return send_whatsapp_message(recipient_id, message_data)

def send_order_status_update(recipient_id, order_id, status, tracking_number=None):
    """Send an order status update using a template"""
    components = [
        {
            "type": "body",
            "parameters": [
                {
                    "type": "text",
                    "text": order_id
                },
                {
                    "type": "text",
                    "text": status
                }
            ]
        }
    ]
    
    if tracking_number:
        components[0]["parameters"].append({
            "type": "text",
            "text": tracking_number
        })
        template_name = "order_status_with_tracking"
    else:
        template_name = "order_status_update"
    
    return send_template_message(recipient_id, template_name, "en_US", components)