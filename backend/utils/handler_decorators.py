"""
Handler Decorators
Wrappers for Telegram handlers with error handling and recovery
"""
import logging
from functools import wraps
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)


def safe_handler(fallback_state=ConversationHandler.END, error_message="❌ Произошла ошибка. Попробуйте позже.", skip_maintenance_check=False):
    """
    Decorator for Telegram handlers with automatic error handling
    
    Features:
    - Checks maintenance mode (unless skip_maintenance_check=True)
    - Catches all exceptions
    - Logs error with context
    - Sends user-friendly error message
    - Returns fallback conversation state
    - Prevents bot hangs
    
    Usage:
        @safe_handler(fallback_state=ConversationHandler.END)
        async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # Your handler code
            return NEXT_STATE
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            try:
                # Check maintenance mode (unless explicitly skipped)
                if not skip_maintenance_check:
                    from utils.maintenance_check import check_maintenance_mode
                    if await check_maintenance_mode(update):
                        maintenance_msg = (
                            "🔧 *Технические работы*\n\n"
                            "Уважаемый пользователь!\n\n"
                            "В данный момент проводятся плановые технические работы для улучшения качества сервиса.\n\n"
                            "⏰ Примерное время: 10-15 минут\n"
                            "✅ Все ваши данные и заказы сохранены\n"
                            "📱 Бот вернется к работе в ближайшее время\n\n"
                            "Приносим извинения за временные неудобства!\n"
                            "Спасибо за понимание 🙏"
                        )
                        try:
                            if update.message:
                                await update.message.reply_text(maintenance_msg, parse_mode='Markdown')
                            elif update.callback_query:
                                await update.callback_query.answer("⏳ Технические работы", show_alert=True)
                                await update.callback_query.message.reply_text(maintenance_msg, parse_mode='Markdown')
                        except Exception as e:
                            logger.error(f"Failed to send maintenance message: {e}")
                        return fallback_state
                
                # Call original handler
                return await func(update, context, *args, **kwargs)
                
            except Exception as e:
                # Extract context info
                user_id = update.effective_user.id if update.effective_user else "Unknown"
                chat_id = update.effective_chat.id if update.effective_chat else "Unknown"
                handler_name = func.__name__
                
                # Log with full context
                logger.error(
                    f"❌ Error in handler '{handler_name}' "
                    f"(user_id={user_id}, chat_id={chat_id}): {type(e).__name__}: {str(e)}",
                    exc_info=True
                )
                
                # Send error notification to admin
                try:
                    import os
                    from telegram import Bot
                    admin_id = os.getenv('ADMIN_TELEGRAM_ID')
                    if admin_id:
                        bot = Bot(os.getenv('TELEGRAM_BOT_TOKEN'))
                        error_text = f"""🚨 *Ошибка в боте*
━━━━━━━━━━━━━━━━━━━━

👤 *User ID:* `{user_id}`
💬 *Chat ID:* `{chat_id}`
⚙️ *Handler:* `{handler_name}`

❌ *Error:* {type(e).__name__}
📝 *Details:* {str(e)[:200]}

🕐 *Time:* {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M UTC')}"""
                        
                        await bot.send_message(
                            chat_id=admin_id,
                            text=error_text,
                            parse_mode='Markdown'
                        )
                except Exception as admin_error:
                    logger.error(f"Failed to send error notification to admin: {admin_error}")
                
                # Send error message to user
                try:
                    if update.message:
                        await update.message.reply_text(error_message)
                    elif update.callback_query:
                        await update.callback_query.answer(error_message, show_alert=True)
                        await update.callback_query.message.reply_text(error_message)
                except Exception as send_error:
                    logger.error(f"Failed to send error message: {send_error}")
                
                # Return fallback state to prevent hang
                return fallback_state
        
        return wrapper
    return decorator


def track_handler_performance(threshold_seconds=2.0):
    """
    Decorator to track handler execution time
    
    Logs warning if handler takes too long
    
    Usage:
        @track_handler_performance(threshold_seconds=2.0)
        async def slow_handler(update, context):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            import time
            
            handler_name = func.__name__
            start_time = time.perf_counter()
            
            try:
                result = await func(update, context, *args, **kwargs)
                return result
            finally:
                elapsed = time.perf_counter() - start_time
                
                if elapsed > threshold_seconds:
                    user_id = update.effective_user.id if update.effective_user else "Unknown"
                    logger.warning(
                        f"⏱️ SLOW HANDLER: '{handler_name}' took {elapsed:.2f}s "
                        f"(user_id={user_id}, threshold={threshold_seconds}s)"
                    )
                else:
                    logger.debug(f"✅ Handler '{handler_name}' completed in {elapsed:.2f}s")
        
        return wrapper
    return decorator


def require_session(fallback_state=ConversationHandler.END):
    """
    Decorator to ensure session exists before handler execution
    
    If session missing, creates new one and notifies user
    
    Usage:
        @require_session(fallback_state=ConversationHandler.END)
        async def handler_needs_session(update, context):
            # Session guaranteed to exist
            session = context.user_data['session']
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            from session_manager import session_manager
            
            user_id = update.effective_user.id
            
            # Check if session exists
            session = await session_manager.get_session(user_id)
            
            if not session:
                logger.warning(f"⚠️ Session missing for user {user_id} in handler '{func.__name__}', creating new one")
                
                # Create new session
                session = await session_manager.get_or_create_session(user_id)
                
                # Notify user
                message = "⚠️ Сессия истекла. Начнем заново."
                if update.message:
                    await update.message.reply_text(message)
                elif update.callback_query:
                    await update.callback_query.answer(message, show_alert=True)
                
                return fallback_state
            
            # Store in context for handler
            context.user_data['session'] = session
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


def with_typing_action():
    """
    Decorator to show "typing..." action during handler execution
    
    Provides visual feedback to user that bot is working
    
    Usage:
        @with_typing_action()
        async def long_running_handler(update, context):
            # Bot shows "typing..." while this runs
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            import asyncio
            from telegram.constants import ChatAction
            
            # 🚀 PERFORMANCE: Send typing action in background - don't block handler
            if update.effective_chat:
                async def send_typing():
                    try:
                        await context.bot.send_chat_action(
                            chat_id=update.effective_chat.id,
                            action=ChatAction.TYPING
                        )
                    except Exception as e:
                        logger.debug(f"Failed to send typing action: {e}")
                
                asyncio.create_task(send_typing())
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


# ============================================================
# REPOSITORY DECORATORS (New Phase 3)
# ============================================================

def with_user_check(create_if_missing=True):
    """
    Decorator to ensure user exists in database
    
    Automatically creates user if missing (optional)
    Injects user object into context.user_data['db_user']
    
    Usage:
        @with_user_check(create_if_missing=True)
        async def my_handler(update, context):
            user = context.user_data['db_user']
            # User guaranteed to exist
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            from repositories import get_user_repo
            
            user_id = update.effective_user.id
            username = update.effective_user.username
            first_name = update.effective_user.first_name
            last_name = update.effective_user.last_name
            
            user_repo = get_user_repo()
            
            if create_if_missing:
                # Get or create user
                user = await user_repo.get_or_create_user(
                    telegram_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
            else:
                # Just find
                user = await user_repo.find_by_telegram_id(user_id)
                
                if not user:
                    logger.warning(f"⚠️ User {user_id} not found in database")
                    if update.message:
                        await update.message.reply_text("❌ Пользователь не найден. Используйте /start")
                    return ConversationHandler.END
            
            # Store in context
            context.user_data['db_user'] = user
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


def with_session(session_type="conversation", create_if_missing=True):
    """
    Decorator to ensure session exists using SessionRepository
    
    Injects session into context.user_data['session']
    
    Usage:
        @with_session(session_type="order")
        async def order_handler(update, context):
            session = context.user_data['session']
            # Session guaranteed to exist
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            from repositories import get_session_repo
            
            user_id = update.effective_user.id
            session_repo = get_session_repo()
            
            if create_if_missing:
                session = await session_repo.get_or_create_session(user_id, session_type)
            else:
                session = await session_repo.get_session(user_id, session_type)
                
                if not session:
                    logger.warning(f"⚠️ Session not found for user {user_id}, type {session_type}")
                    if update.message:
                        await update.message.reply_text("❌ Сессия истекла. Используйте /start")
                    return ConversationHandler.END
            
            # Store in context
            context.user_data['session'] = session
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


def with_logging(log_level=logging.INFO):
    """
    Decorator to log handler execution
    
    Logs:
    - Handler entry with user info
    - Handler exit with result
    - Execution time
    
    Usage:
        @with_logging(log_level=logging.INFO)
        async def my_handler(update, context):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            import time
            
            handler_name = func.__name__
            user_id = update.effective_user.id if update.effective_user else "Unknown"
            
            # Log entry
            logger.log(
                log_level,
                f"▶️ Handler '{handler_name}' START (user_id={user_id})"
            )
            
            start_time = time.perf_counter()
            
            try:
                result = await func(update, context, *args, **kwargs)
                elapsed = time.perf_counter() - start_time
                
                # Log exit
                logger.log(
                    log_level,
                    f"✅ Handler '{handler_name}' END (user_id={user_id}, time={elapsed:.2f}s, result={result})"
                )
                
                return result
                
            except Exception as e:
                elapsed = time.perf_counter() - start_time
                
                logger.log(
                    log_level,
                    f"❌ Handler '{handler_name}' ERROR (user_id={user_id}, time={elapsed:.2f}s, error={e})"
                )
                
                raise
        
        return wrapper
    return decorator


def with_admin_check(send_error_message=True):
    """
    Decorator to ensure user is admin
    
    Checks is_admin flag in database
    
    Usage:
        @with_admin_check()
        async def admin_handler(update, context):
            # Only admins can reach here
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            from repositories import get_user_repo
            
            user_id = update.effective_user.id
            user_repo = get_user_repo()
            
            is_admin = await user_repo.is_admin(user_id)
            
            if not is_admin:
                logger.warning(f"⚠️ Non-admin user {user_id} attempted to access admin handler '{func.__name__}'")
                
                if send_error_message:
                    if update.message:
                        await update.message.reply_text("❌ У вас нет прав для этой команды")
                    elif update.callback_query:
                        await update.callback_query.answer("❌ Нет прав", show_alert=True)
                
                return ConversationHandler.END
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


# ============================================================
# COMBINED DECORATORS
# ============================================================

def robust_handler(
    fallback_state=ConversationHandler.END,
    error_message="❌ Произошла ошибка. Попробуйте позже.",
    track_performance=True,
    show_typing=True,
    require_user=True,
    require_session=False,
    session_type="conversation",
    enable_logging=False
):
    """
    All-in-one decorator combining multiple protections (Phase 3 Enhanced)
    
    Features:
    - Error handling
    - Performance tracking
    - Typing indicator
    - User check (from DB)
    - Session validation (optional)
    - Automatic logging (optional)
    
    Usage:
        @robust_handler(
            fallback_state=CONFIRM_DATA,
            require_user=True,
            require_session=True,
            session_type="order"
        )
        async def my_handler(update, context):
            user = context.user_data['db_user']  # Auto-injected
            session = context.user_data['session']  # Auto-injected
            ...
    """
    def decorator(func):
        # Apply decorators in reverse order (inside-out)
        wrapped = func
        
        # Session check (innermost if enabled)
        if require_session:
            wrapped = with_session(session_type=session_type)(wrapped)
        
        # User check
        if require_user:
            wrapped = with_user_check(create_if_missing=True)(wrapped)
        
        # Logging
        if enable_logging:
            wrapped = with_logging(log_level=logging.INFO)(wrapped)
        
        # Typing action
        if show_typing:
            wrapped = with_typing_action()(wrapped)
        
        # Performance tracking
        if track_performance:
            wrapped = track_handler_performance(threshold_seconds=2.0)(wrapped)
        
        # Error handling (outermost)
        wrapped = safe_handler(fallback_state, error_message)(wrapped)
        
        return wrapped
    
    return decorator


# ============================================================
# USAGE EXAMPLES
# ============================================================

"""
Example 1: Basic error handling
--------------------------------
from utils.handler_decorators import safe_handler
from telegram.ext import ConversationHandler

@safe_handler(fallback_state=ConversationHandler.END)
async def order_from_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # If error occurs, user gets message and conversation ends
    name = update.message.text
    # ... process name
    return NEXT_STATE


Example 2: Performance tracking
--------------------------------
from utils.handler_decorators import track_handler_performance

@track_handler_performance(threshold_seconds=1.5)
async def fetch_rates_handler(update, context):
    # Logs warning if takes > 1.5s
    rates = await fetch_rates(...)
    return SHOW_RATES


Example 3: Combined robust handler
-----------------------------------
from utils.handler_decorators import robust_handler

@robust_handler(
    fallback_state=CONFIRM_DATA,
    error_message="❌ Не удалось обработать данные",
    track_performance=True,
    show_typing=True
)
async def process_address(update, context):
    # Fully protected handler with all features
    ...


Example 4: Session requirement
-------------------------------
from utils.handler_decorators import require_session, safe_handler

@require_session(fallback_state=ConversationHandler.END)
@safe_handler(fallback_state=ConversationHandler.END)
async def continue_order(update, context):
    # Session guaranteed to exist in context.user_data['session']
    session = context.user_data['session']
    ...
"""


# ============================================================
# SERVICE LAYER DECORATORS (Phase 1 Integration)
# ============================================================

def with_services(
    order_service=False,
    user_service=False,
    session_service=False,
    payment_service=False,
    template_service=False
):
    """
    Decorator to inject services into handler
    
    Automatically provides:
    - OrderService instance
    - UserService instance
    - SessionService instance
    - PaymentService instance
    
    Services are passed as keyword arguments to handler
    
    Usage:
        @with_services(user_service=True, session_service=True)
        async def my_handler(update, context, user_service, session_service):
            # Services ready to use
            user = await user_service.get_user(telegram_id)
            session = await session_service.get_session(telegram_id)
    
    Args:
        order_service: Inject OrderService
        user_service: Inject UserService
        session_service: Inject SessionService
        payment_service: Inject PaymentService
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            from services.service_factory import get_service_factory
            
            # Get service factory
            factory = get_service_factory()
            
            # Inject requested services
            if user_service:
                kwargs['user_service'] = factory.get_user_service()
            
            if order_service:
                kwargs['order_service'] = factory.get_order_service()
            
            if session_service:
                kwargs['session_service'] = factory.get_session_service()
            
            if payment_service:
                kwargs['payment_service'] = factory.get_payment_service()
            
            if template_service:
                kwargs['template_service'] = factory.get_template_service()
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


def with_user_session(create_user=True, require_session=False):
    """
    Lazy-loading decorator for user check and context preparation
    
    ⚠️ GOLDEN STANDARD 2025: MongoDBPersistence + Lazy Loading
    
    2025 CRITICAL FIX: Use update.effective_message instead of update.message
    to handle both 'message' and 'edited_message' updates properly!
    
    Architecture:
    1. MongoDBPersistence is the ONLY owner of:
       - ConversationHandler state
       - ALL context.user_data (saves/restores it completely)
    
    2. This decorator does LAZY loading:
       - Checks if db_user already exists in context.user_data (restored by MongoDBPersistence)
       - If YES → reuse it (no DB query!)
       - If NO → load from DB and inject into context
       - MongoDBPersistence will automatically persist it for next handler
    
    Usage:
        @with_user_session()
        async def order_handler(update, context):
            user = context.user_data['db_user']  # Available (lazy-loaded or restored)
            # MongoDBPersistence manages conversation state
    
    Args:
        create_user: Create user if missing (default: True)
        require_session: Ignored (kept for backward compatibility)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            from repositories import get_user_repo
            
            # ✅ 2025 FIX: Use effective_message (works for message AND edited_message)
            message = update.effective_message
            
            # Safety check: ignore if no message and no callback_query
            if not message and not update.callback_query:
                logger.debug(f"⏭️ Ignoring update without message or callback_query")
                return  # Don't block, just skip
            
            user_id = update.effective_user.id
            username = update.effective_user.username
            first_name = update.effective_user.first_name
            handler_name = func.__name__
            
            # ✅ LAZY LOADING: Check if db_user already exists (restored by MongoDBPersistence)
            if 'db_user' in context.user_data:
                user = context.user_data['db_user']
                logger.debug(f"♻️ [{handler_name}] user={user_id}: Reusing cached db_user (no DB query)")
            else:
                # First time or after context clear - load from DB
                logger.debug(f"🔍 [{handler_name}] user={user_id}: Loading db_user from DB")
                
                user_repo = get_user_repo()
                
                if create_user:
                    user = await user_repo.get_or_create_user(
                        telegram_id=user_id,
                        username=username,
                        first_name=first_name
                    )
                else:
                    user = await user_repo.find_by_telegram_id(user_id)
                    if not user:
                        logger.warning(f"❌ [{handler_name}] user={user_id}: User not found")
                        # Use effective_message for reply
                        if message:
                            await message.reply_text("❌ Пользователь не найден. Используйте /start")
                        return ConversationHandler.END
                
                # Inject into context - MongoDBPersistence will persist it automatically
                context.user_data['db_user'] = user
                logger.debug(f"✅ [{handler_name}] user={user_id}: db_user cached for future handlers")
            
            # CRITICAL: Check if blocked (ALWAYS from DB, never from cache!)
            # Re-fetch user from DB to get latest blocked status
            user_repo = get_user_repo()
            fresh_user = await user_repo.find_by_telegram_id(user_id)
            
            if fresh_user and fresh_user.get('blocked', False):
                logger.warning(f"🚫 [{handler_name}] user={user_id}: BLOCKED - denying access")
                # Use effective_message for reply
                if message:
                    await message.reply_text("⛔️ *АККАУНТ ЗАБЛОКИРОВАН*\n\n🚫 Ваш доступ к боту ограничен администратором.\n\n📞 Для разблокировки обратитесь в поддержку.", parse_mode='Markdown')
                elif update.callback_query:
                    await update.callback_query.message.reply_text("⛔️ *АККАУНТ ЗАБЛОКИРОВАН*\n\n🚫 Ваш доступ к боту ограничен администратором.\n\n📞 Для разблокировки обратитесь в поддержку.", parse_mode='Markdown')
                return ConversationHandler.END
            
            # ✅ CRITICAL: DO NOT touch session or conversation state!
            # ✅ MongoDBPersistence is the ONLY manager of conversation state
            
            logger.debug(f"▶️ [{handler_name}] user={user_id}: Calling handler")
            result = await func(update, context, *args, **kwargs)
            logger.debug(f"✅ [{handler_name}] user={user_id}: Handler completed, state={result}")
            
            return result
        
        return wrapper
    return decorator

