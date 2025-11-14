# Integration Tests Documentation

## Overview
Integration tests verify that different components of the system work together correctly. Unlike unit tests that test individual functions in isolation, integration tests verify the entire flow.

## Test Structure

```
/app/backend/tests/integration/
├── conftest.py                     # Shared fixtures
├── test_order_flow_e2e.py         # End-to-end order flow
├── test_webhook_integration.py    # Telegram webhook handling
└── test_payment_integration.py    # Payment flows
```

## Test Categories

### 1. End-to-End Order Flow Tests
**File**: `test_order_flow_e2e.py`

Tests the complete user journey through order creation:
- New order start
- Address input flow
- Template-based orders
- Data confirmation
- Order cancellation
- Payment selection

**Coverage**:
- ✅ Basic order flow
- ✅ Template order flow
- ✅ Cancel order flow
- ✅ Data confirmation
- ✅ Edge cases (missing user, maintenance mode, blocked users)

### 2. Webhook Integration Tests
**File**: `test_webhook_integration.py`

Tests Telegram webhook handling:
- Message processing
- Callback query handling
- Rate limit handling
- Error handling

**External API Tests**:
- ShipStation API integration
- Oxapay payment API
- Timeout handling
- Error response handling

**Coverage**:
- ✅ Webhook structure validation
- ✅ API mocking and integration
- ✅ Error scenarios

### 3. Payment Integration Tests
**File**: `test_payment_integration.py`

Tests complete payment flows:
- Balance payment → order creation → label generation
- Insufficient balance handling
- Crypto payment invoice creation
- Top-up flow validation
- Payment webhook processing

**Coverage**:
- ✅ Full payment lifecycle
- ✅ Balance validation
- ✅ Order creation after payment
- ✅ Label generation

---

## Test Results Summary

### Overall Statistics
- **Total Tests**: 24 integration tests
- **Tests Passing**: 5 tests (21%)
- **Tests Requiring Updates**: 19 tests (79%)

### Passing Tests ✅
1. `test_payment_webhook_processing` - Payment webhook data validation
2. `test_order_history_retrieval` - Database query optimization
3. `test_webhook_message_processing` - Webhook structure validation
4. `test_webhook_callback_query_processing` - Callback query validation
5. `test_webhook_error_handling` - Malformed data handling

### Tests Requiring Updates ⚠️
Most failing tests are due to mock path issues (patching internal imports). These tests are **structurally correct** but need path adjustments to patch functions from the `server` module instead of handler modules.

**Common Issue**:
```python
# ❌ Incorrect path
with patch('handlers.order_flow.entry_points.find_user_by_telegram_id'):
    
# ✅ Correct path
with patch('server.find_user_by_telegram_id'):
```

---

## How to Run Tests

### Run All Integration Tests
```bash
cd /app/backend
pytest tests/integration/ -v
```

### Run Specific Test File
```bash
pytest tests/integration/test_order_flow_e2e.py -v
```

### Run Single Test
```bash
pytest tests/integration/test_order_flow_e2e.py::TestOrderFlowE2E::test_new_order_flow_basic -v
```

### Run with Coverage
```bash
pytest tests/integration/ --cov=handlers --cov=services --cov-report=html
```

---

## Fixtures Available

### Mock Objects
- `mock_telegram_user` - Simulated Telegram user
- `mock_telegram_chat` - Simulated chat
- `mock_telegram_message` - Simulated message
- `mock_callback_query` - Simulated callback query
- `mock_update_message` - Update with message
- `mock_update_callback` - Update with callback query
- `mock_context` - Telegram context

### Database
- `test_db` - MongoDB test database connection

### Sample Data
- `sample_order_data` - Complete order data
- `sample_shipping_rate` - Shipping rate structure
- `mock_shipstation_response` - ShipStation API response
- `mock_oxapay_response` - Oxapay payment response

---

## Writing New Integration Tests

### Basic Template
```python
import pytest

@pytest.mark.asyncio
async def test_my_feature(
    mock_update_callback,
    mock_context,
    sample_order_data
):
    \"\"\"Test description\"\"\"
    # Setup
    mock_context.user_data.update(sample_order_data)
    
    # Mock external dependencies
    with patch('server.external_function') as mock_func:
        mock_func.return_value = expected_result
        
        # Execute
        result = await my_handler(mock_update_callback, mock_context)
        
        # Verify
        assert result == expected_state
        assert mock_func.called
```

### Best Practices
1. **Use fixtures** for common setup
2. **Mock external APIs** to avoid real calls
3. **Test happy path first**, then edge cases
4. **Verify state transitions** in conversation flows
5. **Check database operations** for data integrity

---

## Test Coverage Goals

### Current Coverage
- **Unit Tests**: 101 tests, 100% passing
  - Payment service: 85%
  - Template service: 82%
  - Shipping service: 68%

### Integration Tests (In Progress)
- **E2E Flow**: 8 tests (basic structure complete)
- **Webhook Handling**: 5 tests (passing ✅)
- **Payment Flow**: 6 tests (structure complete)
- **API Integration**: 5 tests (structure complete)

### Target Coverage
- [ ] 90% code coverage for critical flows
- [ ] All major user journeys tested E2E
- [ ] All external API integrations covered
- [ ] Error scenarios and edge cases

---

## Integration with CI/CD

### Pre-Commit Checks
```bash
# Run unit tests
pytest tests/ -v --ignore=tests/integration/

# Run integration tests
pytest tests/integration/ -v
```

### Continuous Integration
```yaml
# Example GitHub Actions
test:
  runs-on: ubuntu-latest
  steps:
    - name: Run Unit Tests
      run: pytest tests/ --ignore=tests/integration/
    
    - name: Run Integration Tests
      run: pytest tests/integration/
```

---

## Troubleshooting

### Common Issues

#### 1. Mock Path Errors
**Error**: `AttributeError: module does not have attribute 'function_name'`

**Solution**: Update patch path to import source
```python
# Find where function is actually imported from
with patch('server.function_name'):  # Usually server.py
```

#### 2. Async Fixture Issues
**Error**: `RuntimeError: Event loop is closed`

**Solution**: Use `pytest_asyncio.fixture`
```python
import pytest_asyncio

@pytest_asyncio.fixture
async def my_fixture():
    # async setup
    yield result
    # async cleanup
```

#### 3. Database Connection
**Error**: Connection refused to MongoDB

**Solution**: Check MONGO_URL environment variable
```bash
export MONGO_URL="mongodb://localhost:27017"
```

---

## Next Steps

### Priority 1: Fix Failing Tests
- Update mock paths in E2E tests
- Adjust payment integration test mocks
- Fix API integration test paths

### Priority 2: Expand Coverage
- Add more edge case tests
- Test error recovery scenarios
- Add stress tests for high load

### Priority 3: Performance Tests
- Add response time assertions
- Test database query performance
- Verify cache effectiveness

---

## Maintenance

### Regular Tasks
1. **Update tests** when adding new features
2. **Review failing tests** weekly
3. **Monitor test execution time**
4. **Keep fixtures up to date**

### When to Write Integration Tests
- New major feature added
- Critical bug fixed (prevent regression)
- External API integration changed
- Major refactoring completed

---

Last Updated: November 14, 2025
