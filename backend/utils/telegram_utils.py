"""
Telegram Utilities
Вспомогательные функции для работы с Telegram Bot
"""
import random
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Button debouncing tracker (для предотвращения двойных кликов)
button_click_tracker = {}
BUTTON_DEBOUNCE_SECONDS = 1.0


def is_button_click_allowed(user_id: int, button_data: str) -> bool:
    """
    Check if button click is allowed (debouncing)
    Предотвращает множественные быстрые клики по кнопкам
    
    Args:
        user_id: Telegram user ID
        button_data: Data from callback button
    
    Returns:
        True if click is allowed, False if too fast
    """
    current_time = datetime.now(timezone.utc).timestamp()
    
    if user_id not in button_click_tracker:
        button_click_tracker[user_id] = {}
    
    last_click = button_click_tracker[user_id].get(button_data, 0)
    
    if current_time - last_click < BUTTON_DEBOUNCE_SECONDS:
        logger.warning(f"Button click blocked for user {user_id}, button {button_data} - too fast")
        return False
    
    button_click_tracker[user_id][button_data] = current_time
    return True


def generate_random_phone():
    """
    Generate a random valid US phone number
    Генерирует случайный валидный американский номер телефона
    
    Returns:
        str: Phone number in format +1XXXXXXXXXX
    """
    # Generate random US phone number in format +1XXXXXXXXXX
    area_code = random.randint(200, 999)  # Valid area codes start from 200
    exchange = random.randint(200, 999)   # Valid exchanges start from 200
    number = random.randint(1000, 9999)   # Last 4 digits
    return f"+1{area_code}{exchange}{number}"


async def generate_thank_you_message():
    """
    Generate a unique thank you message using AI
    Генерирует уникальное сообщение благодарности с помощью AI
    
    Returns:
        str: Thank you message in Russian
    """
    try:
        import os
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        emergent_key = os.environ.get('EMERGENT_LLM_KEY')
        print(f"🔑 EMERGENT_LLM_KEY loaded: {bool(emergent_key)}, len={len(emergent_key) if emergent_key else 0}")
        logger.info(f"🔑 EMERGENT_LLM_KEY loaded: {bool(emergent_key)}")
        
        if not emergent_key:
            raise ValueError("EMERGENT_LLM_KEY not found in environment")
        
        # Generate unique session ID
        session_id = f"thanks_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        
        # Initialize chat with model
        chat = LlmChat(
            api_key=emergent_key,
            session_id=session_id,
            system_message="""Ты креативный помощник, создающий уникальные и теплые благодарности клиентам службы доставки на русском языке. 
Твоя задача - генерировать РАЗНООБРАЗНЫЕ сообщения, не повторяя стиль и формулировки. 
Используй разные подходы: иногда официальный тон, иногда более дружеский, варьируй структуру предложений."""
        )
        chat = chat.with_model("openai", "gpt-4o")
        
        # Add randomness to prompts
        import random
        prompts = [
            "Создай краткое благодарственное сообщение клиенту за использование службы доставки (2-3 предложения). Используй тёплый, дружелюбный тон.",
            "Напиши короткое сообщение с благодарностью клиенту сервиса доставки. Сделай его искренним и приятным (2-3 предложения).",
            "Сформулируй благодарность клиенту за выбор нашей службы доставки. Пусть сообщение будет тёплым, но лаконичным (2-3 предложения).",
            "Создай уникальное сообщение благодарности для клиента доставки. Тон - дружелюбный и позитивный (2-3 предложения).",
            "Напиши короткую благодарность клиенту за пользование сервисом доставки. Сделай текст живым и искренним (2-3 предложения)."
        ]
        
        selected_prompt = random.choice(prompts) + " Без эмодзи, только текст."
        user_message = UserMessage(text=selected_prompt)
        
        # Get response
        print(f"🤖 Sending request to AI...")
        response = await chat.send_message(user_message)
        print(f"🤖 AI Response received: {response[:50] if response else 'EMPTY'}...")
        
        if response and len(response.strip()) > 10:
            logger.info(f"✅ Generated AI thank you message: {response[:50]}...")
            print(f"✅ Using AI-generated message")
            return response.strip()
        else:
            raise ValueError("Empty or invalid response from AI")
            
    except Exception as e:
        print(f"❌ AI Error: {e}")
        logger.error(f"Error generating thank you message: {e}")
        # Use varied fallback messages
        fallback_messages = [
            "Спасибо за использование нашего сервиса! Желаем вам приятной доставки.",
            "Благодарим вас за доверие! Надеемся, что наш сервис оправдал ваши ожидания.",
            "Спасибо, что выбрали нас! Мы ценим ваше время и доверие.",
            "Благодарим за заказ! Желаем, чтобы ваша посылка прибыла быстро и в целости.",
            "Спасибо за сотрудничество! Будем рады видеть вас снова."
        ]
        return random.choice(fallback_messages)


def sanitize_string(text: str, max_length: int = 200) -> str:
    """
    Sanitize input string to prevent injection attacks
    Очищает входную строку от потенциально опасных символов
    
    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
    
    Returns:
        str: Sanitized string
    """
    import re
    import html
    
    if not text:
        return ""
    
    # Remove HTML tags
    text = html.escape(text)
    
    # Remove special characters that could be used in injection
    text = re.sub(r'[<>\"\'%;\(\)\{\}\[\]]', '', text)
    
    # Limit length
    text = text[:max_length]
    
    return text.strip()
