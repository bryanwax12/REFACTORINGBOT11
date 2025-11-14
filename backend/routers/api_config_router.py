"""
API Configuration Management Router
Endpoints для управления конфигурацией внешних API
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict
import logging
from handlers.admin_handlers import verify_admin_key
from utils.api_config import get_api_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api-config", tags=["api-configuration"])


@router.get("/status")
async def get_api_config_status():
    """
    Получить статус конфигурации всех API (публичный для мониторинга)
    
    Returns:
        Статус конфигурации (без чувствительных данных)
    """
    config = get_api_config()
    status = config.get_all_keys_status()
    
    return {
        "success": True,
        "status": {
            "environment": status['environment'],
            "shipstation": {
                "test_available": status['shipstation']['test_configured'],
                "prod_available": status['shipstation']['prod_configured'],
                "current_available": status['shipstation']['current_available']
            },
            "oxapay_available": status['oxapay']['configured'],
            "cryptobot_available": status['cryptobot']['configured']
        }
    }


@router.get("/full")
async def get_api_config_full(authenticated: bool = Depends(verify_admin_key)):
    """
    Получить полную конфигурацию API (требует аутентификацию)
    
    Returns:
        Полный статус конфигурации
    """
    config = get_api_config()
    status = config.get_all_keys_status()
    
    return {
        "success": True,
        "config": {
            "environment": status['environment'],
            "shipstation": {
                "test_key": config._mask_key(config.shipstation_test_key) if config.shipstation_test_key else None,
                "prod_key": config._mask_key(config.shipstation_prod_key) if config.shipstation_prod_key else None,
                "default_key": config._mask_key(config.shipstation_default_key) if config.shipstation_default_key else None,
                "test_configured": status['shipstation']['test_configured'],
                "prod_configured": status['shipstation']['prod_configured'],
                "current_available": status['shipstation']['current_available']
            },
            "oxapay": {
                "key": config._mask_key(config.oxapay_api_key) if config.oxapay_api_key else None,
                "configured": status['oxapay']['configured']
            },
            "cryptobot": {
                "token": config._mask_key(config.cryptobot_token) if config.cryptobot_token else None,
                "configured": status['cryptobot']['configured']
            }
        },
        "message": "Full API configuration retrieved (keys masked for security)"
    }


@router.post("/switch-environment")
async def switch_api_environment(
    data: Dict,
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Переключить API окружение (требует аутентификацию)
    
    Body:
        {
            "environment": "test" или "production"
        }
    
    Note:
        Также обновляет api_mode в базе данных
    """
    new_env = data.get('environment', '').lower()
    
    if new_env not in ['test', 'production']:
        raise HTTPException(
            status_code=400,
            detail="Invalid environment. Must be 'test' or 'production'"
        )
    
    config = get_api_config()
    old_env = config.get_current_environment()
    
    if old_env == new_env:
        return {
            "success": True,
            "message": f"Already using {new_env} environment",
            "environment": new_env
        }
    
    try:
        # Переключить в config manager
        config.set_environment(new_env)
        
        # Обновить в базе данных
        from server import db
        await db.settings.update_one(
            {"key": "api_mode"},
            {"$set": {"value": new_env}},
            upsert=True
        )
        
        logger.info(f"✅ API environment switched: {old_env} -> {new_env}")
        
        return {
            "success": True,
            "message": f"API environment switched from {old_env} to {new_env}",
            "old_environment": old_env,
            "new_environment": new_env,
            "note": "Changes applied immediately, no restart required"
        }
    except Exception as e:
        logger.error(f"Failed to switch API environment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test-keys")
async def test_api_keys(authenticated: bool = Depends(verify_admin_key)):
    """
    Протестировать доступность API ключей (требует аутентификацию)
    
    Returns:
        Результаты проверки каждого ключа
    """
    config = get_api_config()
    results = {}
    
    # Тест ShipStation test key
    try:
        key = config.get_shipstation_key('test')
        results['shipstation_test'] = {
            "available": True,
            "key_preview": config._mask_key(key)
        }
    except ValueError as e:
        results['shipstation_test'] = {
            "available": False,
            "error": str(e)
        }
    
    # Тест ShipStation prod key
    try:
        key = config.get_shipstation_key('production')
        results['shipstation_production'] = {
            "available": True,
            "key_preview": config._mask_key(key)
        }
    except ValueError as e:
        results['shipstation_production'] = {
            "available": False,
            "error": str(e)
        }
    
    # Тест Oxapay key
    try:
        key = config.get_oxapay_key()
        results['oxapay'] = {
            "available": True,
            "key_preview": config._mask_key(key)
        }
    except ValueError as e:
        results['oxapay'] = {
            "available": False,
            "error": str(e)
        }
    
    # Тест CryptoBot token
    try:
        token = config.get_cryptobot_token()
        results['cryptobot'] = {
            "available": True,
            "token_preview": config._mask_key(token)
        }
    except ValueError as e:
        results['cryptobot'] = {
            "available": False,
            "error": str(e)
        }
    
    # Подсчитать сводку
    total = len(results)
    available = sum(1 for r in results.values() if r['available'])
    
    return {
        "success": True,
        "results": results,
        "summary": {
            "total": total,
            "available": available,
            "unavailable": total - available,
            "success_rate": f"{(available/total*100):.1f}%"
        }
    }


@router.get("/recommendations")
async def get_api_config_recommendations():
    """
    Получить рекомендации по конфигурации API
    
    Returns:
        Список рекомендаций
    """
    config = get_api_config()
    status = config.get_all_keys_status()
    
    recommendations = []
    
    # Проверка ShipStation
    if not status['shipstation']['test_configured']:
        recommendations.append({
            "type": "warning",
            "service": "ShipStation",
            "message": "TEST API key not configured",
            "suggestion": "Set SHIPSTATION_API_KEY_TEST in .env for test environment"
        })
    
    if not status['shipstation']['prod_configured']:
        recommendations.append({
            "type": "error",
            "service": "ShipStation",
            "message": "PRODUCTION API key not configured",
            "suggestion": "Set SHIPSTATION_API_KEY_PROD in .env - REQUIRED for production"
        })
    
    # Проверка Oxapay
    if not status['oxapay']['configured']:
        recommendations.append({
            "type": "warning",
            "service": "Oxapay",
            "message": "API key not configured",
            "suggestion": "Set OXAPAY_API_KEY in .env for crypto payments"
        })
    
    # Проверка CryptoBot
    if not status['cryptobot']['configured']:
        recommendations.append({
            "type": "warning",
            "service": "CryptoBot",
            "message": "Token not configured",
            "suggestion": "Set CRYPTOBOT_TOKEN in .env for crypto payments"
        })
    
    # Рекомендация по окружению
    current_env = status['environment']
    if current_env == 'production' and not status['shipstation']['prod_configured']:
        recommendations.append({
            "type": "error",
            "service": "System",
            "message": "Production environment without production API keys",
            "suggestion": "Configure production keys or switch to test environment"
        })
    
    return {
        "success": True,
        "current_environment": current_env,
        "recommendations": recommendations,
        "status": "healthy" if len(recommendations) == 0 else "needs_attention"
    }
