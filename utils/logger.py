import logging

def get_logger(name):
    """Get a configured logger for the given name"""
    logger = logging.getLogger(name)
    
    # If no handlers exist, configure one
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    return logger