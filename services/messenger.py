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



def send_media_card_carousel(recipient_id, customer_name, product_category, cards):
    """Send a media card carousel for product browsing based on the template"""
    
    # Prepare cards for the template
    template_cards = []
    
    for idx, card in enumerate(cards):
        # Handle image - use the header_handle format from template
        header_param = {
            "type": "image",
            "image": {
                "id": card.get("image_id", "1220367125959487" )  # Use provided image ID or default
            }
        }
        
        # If image_id is a URL, you'd need to upload it first to get a media ID
        # For this implementation, assuming image_id is already a valid media ID
        
        card_data = {
            "card_index": idx,
            "components": [
                {
                    "type": "header",
                    "parameters": [header_param]
                },
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": card.get("product_name", f"Product {idx + 1}")
                        },
                        {
                            "type": "text", 
                            "text": card.get("price", "GHS199")
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
                            "payload": card.get("quick_reply_payload", f"view_options_{card.get('product_name', f'product_{idx}')}")
                        }
                    ]
                }
            ]
        }
        
        template_cards.append(card_data)

        
    n= len(template_cards)
    print(f"Number of cards in carousel: {n}")
    # Create the message data matching the template structure
    message_data = {
        "type": "template",
        "template": {
            "name": f"browse_product_category_template_v{n}",  # Template name from your JSON
            "language": {
                "code": "en"
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": product_category  # {{2}} - Product category (e.g., "Smartphones")
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



def send_product_card_carousel(recipient_id, products,base_product_name="product"):
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
            "name": "browse_product_options_v3",
            "language": {
                "code": "en_US"
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": base_product_name
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



def send_single_product_message(recipient_id, product):
    """Send a single product message using WhatsApp single_product_option template"""
    from config import CATALOG_ID
    
    if not product:
        logger.error("No product provided for single product message")
        return None
    
    # Ensure required fields exist
    retailer_id = product.get("retailer_id") or product.get("id", "")
    catalog_id = product.get("catalog_id") or CATALOG_ID
    
    if not retailer_id:
        logger.error(f"Product missing retailer_id: {product}")
        return None
    
    # Create the message data using single_product_option template
    message_data = {
        "type": "template",
        "template": {
            "name": "single_product_option",
            "language": {
                "code": "en_US"
            },
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "product",
                            "product": {
                                "product_retailer_id": retailer_id,
                                "catalog_id": catalog_id
                            }
                        }
                    ]
                }
            ]
        }
    }
    
    logger.info(f"Sending single product message for product: {product.get('name', retailer_id)}")
    logger.debug(f"Single product message data: {message_data}")
    
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

def send_location_message(recipient_id, latitude, longitude, name=None, address=None):
    """Send a location message with coordinates and optional name/address"""
    message_data = {
        "type": "location",
        "location": {
            "latitude": latitude,
            "longitude": longitude
        }
    }
    
    # Add name and address if provided
    if name:
        message_data["location"]["name"] = name
    
    if address:
        message_data["location"]["address"] = address
    
    return send_whatsapp_message(recipient_id, message_data)

def send_payment_link_message(user_id, order_id, network, phone_number, payment_url):
    """Send a message with a payment link button using Interactive CTA URL"""
    # First send the informational text
    info_message = (
        # f"Thank you. Your payment will be processed through your {network} mobile money account {phone_number}.\n\n"
        f"Please click the button below to receive a prompt on your phone to complete your payment for Order #{order_id}."
    )

    # send_text_message(user_id, info_message)
    
    # Create the interactive CTA URL message
    message_data = {
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {
                "text": info_message
            },
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": "Complete Payment",
                    "url": payment_url
                }
            }
        }
    }   
    
    return send_whatsapp_message(user_id, message_data)