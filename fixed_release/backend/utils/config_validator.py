"""
Configuration Validator
Валидация всех переменных окружения при запуске приложения
"""
import os
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Ошибка валидации"""
    variable: str
    error_type: str  # 'missing', 'invalid_format', 'invalid_value'
    message: str
    severity: str  # 'critical', 'warning', 'info'


class ConfigValidator:
    """
    Валидатор конфигурации приложения
    
    Проверяет все переменные окружения при запуске:
    - Обязательные переменные
    - Форматы значений
    - Валидные диапазоны
    - Зависимости между переменными
    """
    
    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
        self.info: List[ValidationError] = []
    
    def _add_error(
        self,
        variable: str,
        error_type: str,
        message: str,
        severity: str = 'critical'
    ):
        """Добавить ошибку валидации"""
        error = ValidationError(variable, error_type, message, severity)
        
        if severity == 'critical':
            self.errors.append(error)
        elif severity == 'warning':
            self.warnings.append(error)
        else:
            self.info.append(error)
    
    def validate_required(self, variable: str, description: str = "") -> bool:
        """
        Проверить что переменная существует
        
        Args:
            variable: Имя переменной
            description: Описание для чего нужна
            
        Returns:
            True если существует
        """
        value = os.environ.get(variable)
        
        if not value:
            self._add_error(
                variable,
                'missing',
                f"Required variable {variable} is not set. {description}",
                'critical'
            )
            return False
        
        return True
    
    def validate_optional(
        self,
        variable: str,
        description: str = "",
        recommendation: Optional[str] = None
    ) -> bool:
        """
        Проверить опциональную переменную
        
        Args:
            variable: Имя переменной
            description: Описание
            recommendation: Рекомендация если не установлена
            
        Returns:
            True если существует
        """
        value = os.environ.get(variable)
        
        if not value:
            message = f"Optional variable {variable} is not set. {description}"
            if recommendation:
                message += f" Recommendation: {recommendation}"
            
            self._add_error(variable, 'missing', message, 'info')
            return False
        
        return True
    
    def validate_url(self, variable: str, required: bool = True) -> bool:
        """
        Валидировать URL
        
        Args:
            variable: Имя переменной
            required: Обязательна ли переменная
            
        Returns:
            True если валидна
        """
        value = os.environ.get(variable)
        
        if not value:
            if required:
                self._add_error(variable, 'missing', f"Required URL {variable} is not set", 'critical')
            return not required
        
        # Проверить формат URL
        url_pattern = re.compile(r'^https?://[\w\-.]+(:\d+)?(/.*)?$')
        
        if not url_pattern.match(value):
            self._add_error(
                variable,
                'invalid_format',
                f"{variable} has invalid URL format: {value}",
                'critical' if required else 'warning'
            )
            return False
        
        return True
    
    def validate_telegram_token(self, variable: str, required: bool = True) -> bool:
        """
        Валидировать Telegram bot token
        
        Args:
            variable: Имя переменной
            required: Обязательна ли переменная
            
        Returns:
            True если валиден
        """
        value = os.environ.get(variable)
        
        if not value:
            if required:
                self._add_error(
                    variable,
                    'missing',
                    f"Required Telegram token {variable} is not set",
                    'critical'
                )
            return not required
        
        # Формат Telegram token: число:строка
        token_pattern = re.compile(r'^\d+:[A-Za-z0-9_-]+$')
        
        if not token_pattern.match(value):
            self._add_error(
                variable,
                'invalid_format',
                f"{variable} has invalid Telegram token format",
                'critical' if required else 'warning'
            )
            return False
        
        return True
    
    def validate_integer(
        self,
        variable: str,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        required: bool = True
    ) -> bool:
        """
        Валидировать целое число
        
        Args:
            variable: Имя переменной
            min_value: Минимальное значение
            max_value: Максимальное значение
            required: Обязательна ли переменная
            
        Returns:
            True если валидно
        """
        value = os.environ.get(variable)
        
        if not value:
            if required:
                self._add_error(variable, 'missing', f"Required integer {variable} is not set", 'critical')
            return not required
        
        try:
            int_value = int(value)
            
            # Проверить диапазон
            if min_value is not None and int_value < min_value:
                self._add_error(
                    variable,
                    'invalid_value',
                    f"{variable} value {int_value} is less than minimum {min_value}",
                    'warning'
                )
                return False
            
            if max_value is not None and int_value > max_value:
                self._add_error(
                    variable,
                    'invalid_value',
                    f"{variable} value {int_value} is greater than maximum {max_value}",
                    'warning'
                )
                return False
            
            return True
            
        except ValueError:
            self._add_error(
                variable,
                'invalid_format',
                f"{variable} is not a valid integer: {value}",
                'critical' if required else 'warning'
            )
            return False
    
    def validate_enum(
        self,
        variable: str,
        allowed_values: List[str],
        required: bool = True,
        case_sensitive: bool = False
    ) -> bool:
        """
        Валидировать enum значение
        
        Args:
            variable: Имя переменной
            allowed_values: Разрешенные значения
            required: Обязательна ли переменная
            case_sensitive: Учитывать регистр
            
        Returns:
            True если валидно
        """
        value = os.environ.get(variable)
        
        if not value:
            if required:
                self._add_error(
                    variable,
                    'missing',
                    f"Required variable {variable} is not set. Allowed: {allowed_values}",
                    'critical'
                )
            return not required
        
        # Проверить значение
        check_value = value if case_sensitive else value.lower()
        check_allowed = allowed_values if case_sensitive else [v.lower() for v in allowed_values]
        
        if check_value not in check_allowed:
            self._add_error(
                variable,
                'invalid_value',
                f"{variable} has invalid value '{value}'. Allowed: {allowed_values}",
                'critical' if required else 'warning'
            )
            return False
        
        return True
    
    def validate_conditional(
        self,
        condition_var: str,
        condition_value: str,
        required_var: str,
        description: str = ""
    ) -> bool:
        """
        Валидировать условную зависимость
        
        Args:
            condition_var: Переменная условия
            condition_value: Значение условия
            required_var: Обязательная переменная если условие истинно
            description: Описание зависимости
            
        Returns:
            True если валидно
        """
        cond_value = os.environ.get(condition_var, '').lower()
        
        if cond_value == condition_value.lower():
            # Условие выполнено, проверить зависимую переменную
            if not os.environ.get(required_var):
                self._add_error(
                    required_var,
                    'missing',
                    f"{required_var} is required when {condition_var}={condition_value}. {description}",
                    'critical'
                )
                return False
        
        return True
    
    def validate_all(self) -> Tuple[bool, Dict]:
        """
        Выполнить полную валидацию конфигурации
        
        Returns:
            (is_valid, report)
        """
        logger.info("🔍 Starting configuration validation...")
        
        # ============================================================
        # CRITICAL: Database
        # ============================================================
        self.validate_required('MONGO_URL', 'MongoDB connection string required')
        
        # ============================================================
        # CRITICAL: Telegram Bot
        # ============================================================
        self.validate_telegram_token('TEST_BOT_TOKEN', required=False)
        self.validate_telegram_token('PROD_BOT_TOKEN', required=False)
        
        # Хотя бы один токен должен быть
        if not os.environ.get('TEST_BOT_TOKEN') and not os.environ.get('PROD_BOT_TOKEN'):
            self._add_error(
                'TELEGRAM_BOT',
                'missing',
                'At least one bot token (TEST_BOT_TOKEN or PROD_BOT_TOKEN) must be configured',
                'critical'
            )
        
        # ============================================================
        # Bot Configuration
        # ============================================================
        self.validate_enum(
            'BOT_ENVIRONMENT',
            ['test', 'production'],
            required=False
        )
        
        self.validate_enum(
            'BOT_MODE',
            ['polling', 'webhook'],
            required=False
        )
        
        # Webhook URL нужен если BOT_MODE=webhook
        self.validate_conditional(
            'BOT_MODE',
            'webhook',
            'WEBHOOK_BASE_URL',
            'Webhook URL is required for webhook mode'
        )
        
        if os.environ.get('WEBHOOK_BASE_URL'):
            self.validate_url('WEBHOOK_BASE_URL', required=False)
        
        # ============================================================
        # API Keys
        # ============================================================
        self.validate_optional(
            'SHIPSTATION_API_KEY_TEST',
            'ShipStation test API key',
            'Set for test environment'
        )
        
        self.validate_optional(
            'SHIPSTATION_API_KEY_PROD',
            'ShipStation production API key',
            'Set for production environment'
        )
        
        self.validate_optional(
            'OXAPAY_API_KEY',
            'Oxapay payment gateway key',
            'Set if using Oxapay for payments'
        )
        
        self.validate_optional(
            'CRYPTOBOT_TOKEN',
            'CryptoBot payment token',
            'Set if using CryptoBot for payments'
        )
        
        # ============================================================
        # Admin Configuration
        # ============================================================
        self.validate_integer(
            'ADMIN_TELEGRAM_ID',
            min_value=1,
            required=False
        )
        
        self.validate_optional(
            'ADMIN_API_KEY',
            'Admin API key for protected endpoints',
            'Generate secure random key'
        )
        
        # ============================================================
        # Optional Configuration
        # ============================================================
        self.validate_optional(
            'SENTRY_DSN',
            'Sentry error tracking DSN',
            'Set up Sentry for production error tracking'
        )
        
        # ============================================================
        # Generate Report
        # ============================================================
        is_valid = len(self.errors) == 0
        
        report = {
            'is_valid': is_valid,
            'errors': [
                {
                    'variable': e.variable,
                    'type': e.error_type,
                    'message': e.message,
                    'severity': e.severity
                }
                for e in self.errors
            ],
            'warnings': [
                {
                    'variable': w.variable,
                    'type': w.error_type,
                    'message': w.message,
                    'severity': w.severity
                }
                for w in self.warnings
            ],
            'info': [
                {
                    'variable': i.variable,
                    'type': i.error_type,
                    'message': i.message,
                    'severity': i.severity
                }
                for i in self.info
            ],
            'summary': {
                'critical_errors': len(self.errors),
                'warnings': len(self.warnings),
                'info': len(self.info)
            }
        }
        
        # Логирование
        if is_valid:
            logger.info("✅ Configuration validation passed")
            if self.warnings:
                logger.warning(f"⚠️ {len(self.warnings)} warnings found")
        else:
            logger.error(f"❌ Configuration validation failed with {len(self.errors)} errors")
        
        return is_valid, report
    
    def print_report(self, report: Dict):
        """
        Вывести читаемый отчет валидации
        
        Args:
            report: Отчет от validate_all()
        """
        print("\n" + "="*60)
        print("📋 CONFIGURATION VALIDATION REPORT")
        print("="*60)
        
        # Summary
        summary = report['summary']
        print("\n📊 Summary:")
        print(f"   Critical Errors: {summary['critical_errors']}")
        print(f"   Warnings: {summary['warnings']}")
        print(f"   Info: {summary['info']}")
        
        # Errors
        if report['errors']:
            print(f"\n❌ Critical Errors ({len(report['errors'])}):")
            for err in report['errors']:
                print(f"   • {err['variable']}: {err['message']}")
        
        # Warnings
        if report['warnings']:
            print(f"\n⚠️  Warnings ({len(report['warnings'])}):")
            for warn in report['warnings']:
                print(f"   • {warn['variable']}: {warn['message']}")
        
        # Info
        if report['info']:
            print(f"\nℹ️  Info ({len(report['info'])}):")
            for info in report['info']:
                print(f"   • {info['variable']}: {info['message']}")
        
        # Status
        print(f"\n{'='*60}")
        if report['is_valid']:
            print("✅ Configuration is VALID - Application can start")
        else:
            print("❌ Configuration is INVALID - Fix errors before starting")
        print("="*60 + "\n")


def validate_configuration(print_report: bool = True) -> Tuple[bool, Dict]:
    """
    Валидировать конфигурацию приложения
    
    Args:
        print_report: Вывести отчет в консоль
        
    Returns:
        (is_valid, report)
    """
    validator = ConfigValidator()
    is_valid, report = validator.validate_all()
    
    if print_report:
        validator.print_report(report)
    
    return is_valid, report


"""
ИСПОЛЬЗОВАНИЕ:
=============

1. В server.py при запуске:
   ```python
   from utils.config_validator import validate_configuration
   
   # Перед startup
   is_valid, report = validate_configuration(print_report=True)
   
   if not is_valid:
       logger.critical("Configuration validation failed!")
       raise SystemExit(1)
   ```

2. Проверка из CLI:
   ```bash
   python -c "from utils.config_validator import validate_configuration; validate_configuration()"
   ```

ПРЕИМУЩЕСТВА:
=============

- ✅ Fail-fast при неправильной конфигурации
- ✅ Понятные сообщения об ошибках
- ✅ Документация обязательных переменных
- ✅ Проверка форматов и значений
- ✅ Conditional validation (зависимости)
- ✅ Рекомендации по настройке
"""
