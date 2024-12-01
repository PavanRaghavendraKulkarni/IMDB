import logging

def get_logger(name):
    """
    Returns a logger instance configured to log to the console.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)  
        formatter = logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    return logger
