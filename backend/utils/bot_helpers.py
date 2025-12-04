"""
Bot Helper Functions
Provides safe access to bot_instance without circular imports
"""

def get_bot_instance():
    """
    Get bot_instance safely without circular imports
    Import inside function to avoid circular dependency
    """
    from server import bot_instance
    return bot_instance

def get_application():
    """
    Get application safely without circular imports
    """
    from server import application
    return application
