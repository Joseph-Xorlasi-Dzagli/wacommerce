from pyngrok import ngrok
from utils.logger import get_logger

logger = get_logger(__name__)

def start_ngrok_tunnel(port=5000):
    """Start ngrok HTTP tunnel"""
    try:
        public_url = ngrok.connect(port).public_url
        logger.info(f"ngrok tunnel started at: {public_url}")
        webhook_url = f"{public_url}/webhook"
        logger.info(f"Webhook URL for WhatsApp API configuration: {webhook_url}")
        print(f"\n* Webhook URL for WhatsApp API configuration: {webhook_url}\n")
        return webhook_url
    except Exception as e:
        logger.error(f"Failed to start ngrok tunnel: {str(e)}")
        return None

def stop_ngrok():
    """Stop all ngrok tunnels"""
    try:
        ngrok.kill()
        logger.info("All ngrok tunnels closed")
    except Exception as e:
        logger.error(f"Error closing ngrok tunnels: {str(e)}")