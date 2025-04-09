# WhatsApp eCommerce Bot

A comprehensive WhatsApp eCommerce solution that enables customers to browse products, place orders, and get customer support directly through WhatsApp messaging.

## Features

- **Conversational Interface**: Natural language processing to understand customer intent
- **Product Catalog**: Browse categories and products from your WhatsApp Business catalog
- **Shopping Cart**: Add, remove, and view items in cart
- **Checkout Process**: Complete purchases with various payment options
- **Order Management**: Track orders and view order history
- **Customer Support**: FAQs, shipping info, returns policy, and agent connection

## Architecture

This application follows a modular design pattern with clear separation of concerns:

- **Models**: Data structures for sessions, carts, and orders
- **Services**: Core functionality like catalog management, intent recognition, and messaging
- **Handlers**: Business logic for handling different user intents and interactions
- **Utils**: Utility functions for logging, ngrok tunneling, etc.

## Requirements

- Python 3.8+
- WhatsApp Business API access
- OpenAI API key
- Product catalog set up in WhatsApp Business Manager

## Setup

1. Clone this repository:

```
git clone https://github.com/yourusername/whatsapp-ecommerce-bot.git
cd whatsapp-ecommerce-bot
```

2. Create a virtual environment and install dependencies:

```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Copy the environment template and fill in your credentials:

```
cp .env.template .env
# Edit .env with your actual credentials
```

4. Run the application:

```
python app.py
```

The application will start and display a webhook URL that you can use to configure your WhatsApp Business API.

## Configuration

To set up the WhatsApp integration:

1. Go to the [Meta for Developers](https://developers.facebook.com/) portal
2. Set up a WhatsApp Business application
3. Configure the webhook URL displayed when you start the application
4. Set up your product catalog in WhatsApp Business Manager

## Integrating with ChatGPT

This bot uses OpenAI's GPT models to understand user intent from natural language. You'll need an OpenAI API key to use this feature.

## Customization

You can customize various aspects of the bot:

- **Product Catalog**: Connect to your own database or e-commerce platform
- **Payment Methods**: Integrate with payment gateways
- **Shipping Options**: Configure shipping providers and rates
- **Support Flow**: Customize FAQ content and support team connections

## Project Structure

```
whatsapp_store/
├── app.py                 # Main Flask application entry point
├── config.py              # Configuration and environment variables
├── models/                # Data models
│   ├── session.py         # User session management
│   ├── cart.py            # Shopping cart functionality
│   └── order.py           # Order management
├── services/              # Core services
│   ├── catalog.py         # Product catalog management
│   ├── intent.py          # Intent recognition with OpenAI
│   └── messenger.py       # WhatsApp message sending functionality
├── handlers/              # Intent handlers
│   ├── greeting.py        # Greeting intent handler
│   ├── browse.py          # Browse catalog/product handlers
│   ├── cart.py            # Cart management handlers
│   ├── checkout.py        # Checkout process handlers
│   ├── order.py           # Order status handlers
│   └── support.py         # Customer support handlers
└── utils/                 # Utilities
    ├── logger.py          # Logging configuration
    └── ngrok.py           # Ngrok tunnel management
```

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.