"""
External API Services
Handles communication with ShipStation, Oxapay, and other external services
"""
import os
import logging
import time
import httpx
from fastapi import HTTPException
from utils.retry_utils import retry_on_api_error

logger = logging.getLogger(__name__)

# Configuration from environment
OXAPAY_API_KEY = os.environ.get('OXAPAY_API_KEY', '')
OXAPAY_API_URL = 'https://api.oxapay.com'

# Get ShipStation API key from environment (prefer TEST for sandbox, fallback to PROD, then default)
_PROD_KEY = os.environ.get('SHIPSTATION_API_KEY_PROD')
_TEST_KEY = os.environ.get('SHIPSTATION_API_KEY_TEST')
_DEFAULT_KEY = os.environ.get('SHIPSTATION_API_KEY', '')
SHIPSTATION_API_KEY = _TEST_KEY or _PROD_KEY or _DEFAULT_KEY  # ⚠️ TEST MODE ENABLED

# Debug logging for API key loading
logger.info(f"🔑 ShipStation API Key loading: PROD={'SET' if _PROD_KEY else 'NOT SET'}, TEST={'SET' if _TEST_KEY else 'NOT SET'}, DEFAULT={'SET' if _DEFAULT_KEY else 'NOT SET'}, FINAL={'SET (len={})'.format(len(SHIPSTATION_API_KEY)) if SHIPSTATION_API_KEY else 'NOT SET'}")


@retry_on_api_error(max_attempts=3, min_wait=2, max_wait=10)
async def create_oxapay_invoice(amount: float, order_id: str, description: str = "Shipping Label Payment"):
    """Create payment invoice via Oxapay"""
    if not OXAPAY_API_KEY:
        raise HTTPException(status_code=500, detail="Oxapay API key not configured")
    
    try:
        # Prepare headers with API key
        headers = {
            "merchant_api_key": OXAPAY_API_KEY,
            "Content-Type": "application/json"
        }
        
        # Prepare payload according to official documentation (using camelCase for Oxapay)
        webhook_url = f"{os.environ.get('WEBHOOK_BASE_URL', 'https://telebot-fixer-1.preview.emergentagent.com')}/api/oxapay/webhook"
        payload = {
            "amount": amount,
            "currency": "USD",
            "lifeTime": 30,  # 30 minutes
            "feePaidByPayer": 0,  # Merchant pays fees
            "underPaidCoverage": 2,  # Accept 2% underpayment
            "callbackUrl": webhook_url,
            "returnUrl": f"https://t.me/{os.environ.get('BOT_USERNAME', '')}",
            "description": description,
            "orderId": order_id
        }
        
        logger.info(f"🔗 Creating Oxapay invoice with callbackUrl: {webhook_url}")
        logger.info(f"Creating Oxapay invoice: amount=${amount}, callbackUrl={webhook_url}")
        
        # Profile Oxapay API call (now truly async!)
        api_start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OXAPAY_API_URL}/v1/payment/invoice",
                json=payload,
                headers=headers
            )
        api_duration_ms = (time.perf_counter() - api_start_time) * 1000
        logger.info(f"⚡ Oxapay create invoice API took {api_duration_ms:.2f}ms")
        
        if response.status_code == 200:
            data = response.json()
            # Check for new API format (status 200 with data object)
            if data.get('status') == 200 and 'data' in data:
                invoice_data = data.get('data', {})
                return {
                    'trackId': invoice_data.get('track_id'),
                    'payLink': invoice_data.get('payment_url'),
                    'success': True
                }
            # Check for old API format (result code 100)
            elif data.get('result') == 100:
                return {
                    'trackId': data.get('trackId'),
                    'payLink': data.get('payLink'),
                    'success': True
                }
        
        logger.error(f"Oxapay invoice creation failed: {response.text}")
        return {'success': False, 'error': response.text}
        
    except Exception as e:
        logger.error(f"Oxapay error: {e}")
        return {'success': False, 'error': str(e)}


@retry_on_api_error(max_attempts=3, min_wait=1, max_wait=5)
async def check_oxapay_payment(track_id: str):
    """Check payment status via Oxapay"""
    try:
        # Prepare headers with API key
        headers = {
            "merchant_api_key": OXAPAY_API_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "trackId": track_id
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OXAPAY_API_URL}/v1/payment/info",
                json=payload,
                headers=headers
            )
        
        if response.status_code == 200:
            data = response.json()
            return data
        
        return None
        
    except Exception as e:
        logger.error(f"Oxapay inquiry error: {e}")
        return None


async def check_shipstation_balance():
    """Check ShipStation account balance"""
    try:
        # Import here to avoid circular dependency
        from utils.cache import get_api_mode_cached
        from server import db
        
        api_mode = await get_api_mode_cached(db)
        
        if api_mode == "test":
            logger.info("🧪 Test mode - skipping balance check")
            return {"success": True, "balance": 999.99, "test_mode": True}
        
        # Load API key inside function to ensure env vars are available
        api_key = os.environ.get('SHIPSTATION_API_KEY_TEST') or os.environ.get('SHIPSTATION_API_KEY_PROD') or os.environ.get('SHIPSTATION_API_KEY', '')
        
        if not api_key:
            logger.warning("⚠️ ShipStation API key not configured")
            return {"success": False, "error": "API key not configured"}
        
        headers = {
            "API-Key": api_key,
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                'https://api.shipstation.com/v2/account',
                headers=headers
            )
        
        if response.status_code == 200:
            account_data = response.json()
            balance = account_data.get('balance', 0)
            logger.info(f"💰 ShipStation balance: ${balance}")
            return {"success": True, "balance": balance}
        else:
            logger.error(f"Failed to check balance: {response.status_code} - {response.text}")
            return {"success": False, "error": f"Status {response.status_code}"}
            
    except Exception as e:
        logger.error(f"Balance check error: {e}")
        return {"success": False, "error": str(e)}


@retry_on_api_error(max_attempts=2, min_wait=1, max_wait=5)
async def get_shipstation_carrier_ids():
    """
    Get carrier IDs from ShipStation
    Returns dict mapping carrier names to IDs
    """
    try:
        # Load API key inside function to ensure env vars are available
        api_key = os.environ.get('SHIPSTATION_API_KEY_TEST') or os.environ.get('SHIPSTATION_API_KEY_PROD') or os.environ.get('SHIPSTATION_API_KEY', '')
        
        if not api_key:
            logger.warning("⚠️ ShipStation API key not configured")
            logger.warning("   Checked: SHIPSTATION_API_KEY_PROD, SHIPSTATION_API_KEY_TEST, SHIPSTATION_API_KEY")
            return {}
        
        logger.info(f"✅ ShipStation API key loaded (length: {len(api_key)})")
        
        headers = {
            "API-Key": api_key,
            "Content-Type": "application/json"
        }
        
        logger.info("🔍 Fetching carriers from ShipStation...")
        logger.info("   URL: https://api.shipstation.com/v2/carriers")
        logger.info(f"   API Key (first 10 chars): {api_key[:10]}...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:  # Increased timeout to 30 sec
            response = await client.get(
                'https://api.shipstation.com/v2/carriers',
                headers=headers
            )
        
        logger.info(f"📡 ShipStation carriers response: status={response.status_code}")
        logger.info(f"📡 Response body (first 200 chars): {response.text[:200]}")
        
        if response.status_code == 200:
            try:
                carriers_data = response.json()
                logger.info(f"✅ JSON parsed successfully. Keys: {list(carriers_data.keys())}")
                
                carriers_list = carriers_data.get('carriers', [])
                logger.info(f"✅ Found {len(carriers_list)} carriers in response")
                
                carriers = {}
                
                for idx, carrier in enumerate(carriers_list):
                    carrier_name = carrier.get('name') or carrier.get('friendly_name')
                    carrier_id = carrier.get('carrier_id')
                    
                    if carrier_name and carrier_id:
                        carriers[carrier_name] = carrier_id
                        if idx < 3:  # Log first 3 carriers for debugging
                            logger.info(f"   Carrier {idx+1}: {carrier_name} → {carrier_id}")
                
                logger.info(f"✅ Successfully loaded {len(carriers)} ShipStation carriers")
                return carriers
            except Exception as parse_error:
                logger.error(f"❌ Error parsing carriers response: {parse_error}", exc_info=True)
                logger.error(f"   Response text: {response.text[:500]}")
                return {}
        else:
            logger.error(f"❌ Failed to get carriers: status={response.status_code}")
            logger.error(f"   Response headers: {dict(response.headers)}")
            logger.error(f"   Response body: {response.text[:1000]}")
            return {}
            
    except Exception as e:
        logger.error(f"❌ Error getting ShipStation carriers: {e}", exc_info=True)
        return {}


async def validate_address_with_shipstation(name, street1, street2, city, state, zip_code):
    """
    Validate address with ShipStation API
    Returns (is_valid, corrected_address_or_error_message)
    """
    try:
        # Load API key inside function to ensure env vars are available
        api_key = os.environ.get('SHIPSTATION_API_KEY_TEST') or os.environ.get('SHIPSTATION_API_KEY_PROD') or os.environ.get('SHIPSTATION_API_KEY', '')
        
        if not api_key:
            # If no API key, assume address is valid
            return True, None
        
        headers = {
            "API-Key": api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "name": name,
            "street1": street1,
            "street2": street2 or "",
            "city": city,
            "state": state,
            "postalCode": zip_code,
            "country": "US"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                'https://api.shipstation.com/v2/addresses/validate',
                json=payload,
                headers=headers
            )
        
        if response.status_code == 200:
            data = response.json()
            
            # Check if address is valid
            is_valid = data.get('status') == 'valid'
            
            if not is_valid:
                error_msg = data.get('message', 'Address validation failed')
                return False, error_msg
            
            # Return corrected address if available
            corrected = data.get('address')
            return True, corrected
        else:
            # If validation API fails, don't block user
            logger.warning(f"Address validation failed: {response.status_code}")
            return True, None
            
    except Exception as e:
        logger.error(f"Address validation error: {e}")
        # Don't block user on API errors
        return True, None
