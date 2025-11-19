"""
Centralized Error Handling Middleware
Централизованная обработка ошибок для FastAPI
"""
import logging
import traceback
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import time

logger = logging.getLogger(__name__)


class ErrorResponse:
    """Структурированный формат ответа об ошибке"""
    
    @staticmethod
    def format_error(
        status_code: int,
        error_type: str,
        message: str,
        details: dict = None,
        request_id: str = None
    ) -> dict:
        """
        Форматирование ошибки в единый формат
        
        Args:
            status_code: HTTP status code
            error_type: Тип ошибки (ValidationError, DatabaseError, etc.)
            message: Читаемое сообщение об ошибке
            details: Дополнительные детали (опционально)
            request_id: ID запроса для трейсинга
            
        Returns:
            Словарь с отформатированной ошибкой
        """
        error_response = {
            "error": {
                "type": error_type,
                "message": message,
                "status_code": status_code,
            }
        }
        
        if details:
            error_response["error"]["details"] = details
            
        if request_id:
            error_response["error"]["request_id"] = request_id
            
        return error_response


async def error_handler_middleware(request: Request, call_next):
    """
    Middleware для централизованной обработки ошибок
    
    Перехватывает все необработанные исключения и возвращает
    структурированный JSON ответ
    """
    request_id = str(time.time())  # Простой request ID
    request.state.request_id = request_id
    
    try:
        response = await call_next(request)
        return response
        
    except StarletteHTTPException as e:
        # HTTP исключения (404, 403, etc.)
        logger.warning(
            f"HTTP Error: {e.status_code} - {e.detail}",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "status_code": e.status_code
            }
        )
        
        return JSONResponse(
            status_code=e.status_code,
            content=ErrorResponse.format_error(
                status_code=e.status_code,
                error_type="HTTPError",
                message=str(e.detail),
                request_id=request_id
            )
        )
        
    except RequestValidationError as e:
        # Ошибки валидации Pydantic
        logger.warning(
            f"Validation Error: {e.errors()}",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "validation_errors": e.errors()
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse.format_error(
                status_code=422,
                error_type="ValidationError",
                message="Validation failed",
                details={"errors": e.errors()},
                request_id=request_id
            )
        )
        
    except ValueError as e:
        # Ошибки бизнес-логики
        logger.warning(
            f"Business Logic Error: {str(e)}",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse.format_error(
                status_code=400,
                error_type="BusinessLogicError",
                message=str(e),
                request_id=request_id
            )
        )
        
    except ConnectionError as e:
        # Ошибки подключения (БД, внешние API)
        logger.error(
            f"Connection Error: {str(e)}",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse.format_error(
                status_code=503,
                error_type="ConnectionError",
                message="Service temporarily unavailable. Please try again later.",
                request_id=request_id
            )
        )
        
    except Exception as e:
        # Все остальные неожиданные ошибки
        logger.error(
            f"Unhandled Error: {str(e)}\n{traceback.format_exc()}",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "error_type": type(e).__name__
            }
        )
        
        # В production не показываем детали внутренних ошибок
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse.format_error(
                status_code=500,
                error_type="InternalServerError",
                message="An internal error occurred. Our team has been notified.",
                request_id=request_id
            )
        )


class TelegramErrorHandler:
    """
    Обработчик ошибок для Telegram Bot handlers
    """
    
    @staticmethod
    async def handle_telegram_error(update, context):
        """
        Централизованный обработчик ошибок для Telegram bot
        
        Args:
            update: Telegram Update
            context: Telegram Context
        """
        error = context.error
        
        # Логирование ошибки
        logger.error(
            f"Telegram Bot Error: {str(error)}",
            extra={
                "update": update.to_dict() if update else None,
                "error_type": type(error).__name__,
                "traceback": traceback.format_exc()
            },
            exc_info=True
        )
        
        # Отправка дружественного сообщения пользователю
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "😕 Произошла ошибка при обработке вашего запроса.\n\n"
                    "Мы уже работаем над решением. Пожалуйста, попробуйте позже или "
                    "начните заново с команды /start"
                )
            except Exception as send_error:
                logger.error(f"Failed to send error message to user: {send_error}")
        
        # Отправка уведомления администратору об ошибке
        try:
            from handlers.admin_handlers import notify_admin_error
            from repositories import get_user_repo
            
            # Получаем информацию о пользователе
            if update and update.effective_user:
                user_repo = get_user_repo()
                user = await user_repo.find_by_telegram_id(update.effective_user.id)
                
                if user:
                    error_details = f"{type(error).__name__}: {str(error)[:200]}"
                    await notify_admin_error(
                        user_info=user,
                        error_type="Telegram Bot Error",
                        error_details=error_details
                    )
        except Exception as notify_error:
            logger.error(f"Failed to notify admin about error: {notify_error}")


# Вспомогательные функции для специфических типов ошибок

def is_rate_limit_error(error: Exception) -> bool:
    """Проверка, является ли ошибка превышением rate limit"""
    error_msg = str(error).lower()
    return 'rate limit' in error_msg or 'too many requests' in error_msg


def is_timeout_error(error: Exception) -> bool:
    """Проверка, является ли ошибка timeout"""
    error_msg = str(error).lower()
    return 'timeout' in error_msg or 'timed out' in error_msg


def get_user_friendly_message(error: Exception) -> str:
    """
    Получить дружественное для пользователя сообщение об ошибке
    
    Args:
        error: Exception
        
    Returns:
        Читаемое сообщение для пользователя
    """
    if is_rate_limit_error(error):
        return "Слишком много запросов. Пожалуйста, подождите немного и попробуйте снова."
    
    if is_timeout_error(error):
        return "Запрос занял слишком много времени. Пожалуйста, попробуйте снова."
    
    if isinstance(error, ValueError):
        return str(error)  # ValueError обычно содержит читаемое сообщение
    
    # Для всех остальных ошибок - общее сообщение
    return "Произошла ошибка. Наша команда уже работает над решением."
