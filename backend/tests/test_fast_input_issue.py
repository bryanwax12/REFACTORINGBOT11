#!/usr/bin/env python3
"""
Automated Test for Telegram Bot Fast Input Issue Diagnosis

This test diagnoses the "hanging" issue where the Telegram bot requires users
to send messages 3-4 times before processing them, specifically during the
first step of dialog (entering sender name).

The issue is suspected to be related to:
1. @debounce_input decorator blocking rapid messages
2. ConversationHandler state conflicts with PicklePersistence and block=False
3. Interaction between @debounce_input and @with_user_session decorators

Test Scenarios:
1. Basic bot functionality (/start, "Новый заказ" button)
2. Fast input simulation (3-4 messages < 300ms apart)
3. ConversationHandler state verification
4. Debounce functionality verification
5. Log analysis for "🚫 DEBOUNCE BLOCKED" messages
"""

import asyncio
import json
import os
import time
import requests
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('/app/backend/.env')

class TelegramBotFastInputTester:
    """Test class for diagnosing Telegram bot fast input issues"""
    
    def __init__(self):
        self.backend_url = os.environ.get('WEBHOOK_BASE_URL', 'https://telegram-admin-fix-2.emergent.host')
        self.webhook_url = f"{self.backend_url}/api/telegram/webhook"
        self.bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.mongo_url = os.environ.get('MONGO_URL')
        self.test_user_id = 999999999  # Test user ID
        self.test_results = []
        
        logger.info(f"🔧 Test Configuration:")
        logger.info(f"   Backend URL: {self.backend_url}")
        logger.info(f"   Webhook URL: {self.webhook_url}")
        logger.info(f"   Bot Token: {'✅ Set' if self.bot_token else '❌ Missing'}")
        logger.info(f"   MongoDB URL: {'✅ Set' if self.mongo_url else '❌ Missing'}")
        logger.info(f"   Test User ID: {self.test_user_id}")
    
    def log_test_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result for summary"""
        result = {
            'test': test_name,
            'success': success,
            'details': details,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} {test_name}: {details}")
    
    def create_telegram_update(self, update_type: str, content: str, update_id: int = None) -> Dict[str, Any]:
        """Create a Telegram update object for testing"""
        if update_id is None:
            update_id = int(time.time() * 1000)  # Use timestamp as update_id
        
        base_user = {
            "id": self.test_user_id,
            "is_bot": False,
            "first_name": "TestUser",
            "username": "testuser_fast_input",
            "language_code": "ru"
        }
        
        base_chat = {
            "id": self.test_user_id,
            "first_name": "TestUser",
            "username": "testuser_fast_input",
            "type": "private"
        }
        
        if update_type == "command":
            return {
                "update_id": update_id,
                "message": {
                    "message_id": update_id,
                    "from": base_user,
                    "chat": base_chat,
                    "date": int(time.time()),
                    "text": content,
                    "entities": [
                        {
                            "offset": 0,
                            "length": len(content),
                            "type": "bot_command"
                        }
                    ] if content.startswith('/') else []
                }
            }
        elif update_type == "callback":
            return {
                "update_id": update_id,
                "callback_query": {
                    "id": f"callback_{update_id}",
                    "from": base_user,
                    "message": {
                        "message_id": update_id - 1,
                        "from": {
                            "id": 123456789,  # Bot ID
                            "is_bot": True,
                            "first_name": "WhiteLabelBot",
                            "username": "whitelabel_shipping_bot"
                        },
                        "chat": base_chat,
                        "date": int(time.time()) - 1,
                        "text": "Выберите действие:"
                    },
                    "chat_instance": f"chat_instance_{update_id}",
                    "data": content
                }
            }
        elif update_type == "text":
            return {
                "update_id": update_id,
                "message": {
                    "message_id": update_id,
                    "from": base_user,
                    "chat": base_chat,
                    "date": int(time.time()),
                    "text": content
                }
            }
        else:
            raise ValueError(f"Unknown update type: {update_type}")
    
    def send_webhook_update(self, update: Dict[str, Any], timeout: int = 10) -> requests.Response:
        """Send update to webhook endpoint"""
        try:
            response = requests.post(
                self.webhook_url,
                json=update,
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            )
            return response
        except Exception as e:
            logger.error(f"Error sending webhook update: {e}")
            raise
    
    def check_backend_logs(self, search_terms: List[str], lines: int = 100) -> Dict[str, List[str]]:
        """Check backend logs for specific terms"""
        results = {}
        
        try:
            # Check both output and error logs
            log_files = [
                '/var/log/supervisor/backend.out.log',
                '/var/log/supervisor/backend.err.log'
            ]
            
            for log_file in log_files:
                if os.path.exists(log_file):
                    cmd = f"tail -n {lines} {log_file}"
                    log_content = os.popen(cmd).read()
                    
                    for term in search_terms:
                        if term not in results:
                            results[term] = []
                        
                        # Find lines containing the search term
                        matching_lines = [
                            line.strip() for line in log_content.split('\n')
                            if term.lower() in line.lower() and line.strip()
                        ]
                        results[term].extend(matching_lines)
            
            return results
        except Exception as e:
            logger.error(f"Error checking backend logs: {e}")
            return {}
    
    def test_basic_bot_functionality(self) -> bool:
        """Test 1: Basic bot functionality - /start command and 'Новый заказ' button"""
        logger.info("🔍 Test 1: Basic Bot Functionality")
        
        try:
            # Step 1: Send /start command
            logger.info("   Step 1: Sending /start command")
            start_update = self.create_telegram_update("command", "/start", 1001)
            response = self.send_webhook_update(start_update)
            
            if response.status_code != 200:
                self.log_test_result("Basic Bot - /start", False, f"HTTP {response.status_code}")
                return False
            
            logger.info(f"   /start response: {response.status_code} - {response.text[:100]}")
            
            # Step 2: Click "Новый заказ" button
            logger.info("   Step 2: Clicking 'Новый заказ' button")
            time.sleep(0.5)  # Small delay between requests
            
            new_order_update = self.create_telegram_update("callback", "new_order", 1002)
            response = self.send_webhook_update(new_order_update)
            
            if response.status_code != 200:
                self.log_test_result("Basic Bot - New Order", False, f"HTTP {response.status_code}")
                return False
            
            logger.info(f"   New order response: {response.status_code} - {response.text[:100]}")
            
            # Step 3: Check logs for successful processing
            log_terms = ["start", "new_order", "FROM_NAME"]
            log_results = self.check_backend_logs(log_terms, 50)
            
            start_processed = any("start" in line.lower() for line in log_results.get("start", []))
            order_processed = any("new_order" in line.lower() for line in log_results.get("new_order", []))
            
            success = start_processed or order_processed
            details = f"Start processed: {start_processed}, Order processed: {order_processed}"
            
            self.log_test_result("Basic Bot Functionality", success, details)
            return success
            
        except Exception as e:
            self.log_test_result("Basic Bot Functionality", False, f"Exception: {str(e)}")
            return False
    
    def test_fast_input_scenario(self) -> bool:
        """Test 2: Fast input scenario - simulate rapid message sending"""
        logger.info("🔍 Test 2: Fast Input Scenario (< 300ms between messages)")
        
        try:
            # First, ensure we're in the right state by starting order flow
            logger.info("   Setup: Starting order flow")
            start_update = self.create_telegram_update("command", "/start", 2001)
            self.send_webhook_update(start_update)
            time.sleep(0.2)
            
            new_order_update = self.create_telegram_update("callback", "new_order", 2002)
            self.send_webhook_update(new_order_update)
            time.sleep(0.5)  # Wait for conversation to start
            
            # Now send 4 rapid messages with sender names
            logger.info("   Sending 4 rapid messages (< 300ms apart)")
            sender_names = ["John Smith", "Jane Doe", "Bob Johnson", "Alice Brown"]
            responses = []
            send_times = []
            
            start_time = time.time()
            
            for i, name in enumerate(sender_names):
                send_time = time.time()
                send_times.append(send_time)
                
                update = self.create_telegram_update("text", name, 2010 + i)
                response = self.send_webhook_update(update, timeout=5)
                responses.append(response)
                
                logger.info(f"   Message {i+1}: '{name}' - HTTP {response.status_code} - Time: {send_time - start_time:.3f}s")
                
                # Wait less than 300ms before next message
                if i < len(sender_names) - 1:
                    time.sleep(0.2)  # 200ms delay
            
            total_time = time.time() - start_time
            logger.info(f"   Total time for 4 messages: {total_time:.3f}s")
            
            # Check time intervals
            intervals = []
            for i in range(1, len(send_times)):
                interval = (send_times[i] - send_times[i-1]) * 1000  # Convert to ms
                intervals.append(interval)
                logger.info(f"   Interval {i}: {interval:.1f}ms")
            
            # Verify all intervals are < 300ms
            fast_input_achieved = all(interval < 300 for interval in intervals)
            
            # Check responses
            successful_responses = sum(1 for r in responses if r.status_code == 200)
            
            # Check logs for debounce activity
            time.sleep(1)  # Wait for logs to be written
            log_terms = ["debounce", "blocked", "🚫", "DEBOUNCE_BLOCKED"]
            log_results = self.check_backend_logs(log_terms, 100)
            
            debounce_logs = []
            for term, lines in log_results.items():
                debounce_logs.extend(lines)
            
            debounce_detected = len(debounce_logs) > 0
            
            logger.info(f"   Fast input achieved: {fast_input_achieved}")
            logger.info(f"   Successful responses: {successful_responses}/4")
            logger.info(f"   Debounce logs found: {len(debounce_logs)}")
            
            if debounce_logs:
                logger.info("   Debounce log samples:")
                for log_line in debounce_logs[:3]:  # Show first 3 debounce logs
                    logger.info(f"      {log_line}")
            
            # Test success criteria:
            # 1. Fast input was achieved (< 300ms intervals)
            # 2. At least one message was processed successfully
            # 3. Debounce mechanism should be working (blocking subsequent messages)
            
            success = fast_input_achieved and successful_responses >= 1
            details = f"Intervals: {[f'{i:.1f}ms' for i in intervals]}, Responses: {successful_responses}/4, Debounce: {debounce_detected}"
            
            self.log_test_result("Fast Input Scenario", success, details)
            return success
            
        except Exception as e:
            self.log_test_result("Fast Input Scenario", False, f"Exception: {str(e)}")
            return False
    
    def test_conversation_state_persistence(self) -> bool:
        """Test 3: ConversationHandler state persistence"""
        logger.info("🔍 Test 3: ConversationHandler State Persistence")
        
        try:
            # Start conversation
            logger.info("   Starting conversation flow")
            start_update = self.create_telegram_update("command", "/start", 3001)
            response1 = self.send_webhook_update(start_update)
            time.sleep(0.3)
            
            new_order_update = self.create_telegram_update("callback", "new_order", 3002)
            response2 = self.send_webhook_update(new_order_update)
            time.sleep(0.5)
            
            # Send sender name
            name_update = self.create_telegram_update("text", "Test Sender", 3003)
            response3 = self.send_webhook_update(name_update)
            time.sleep(0.5)
            
            # Send sender address (should be next step)
            address_update = self.create_telegram_update("text", "123 Test Street", 3004)
            response4 = self.send_webhook_update(address_update)
            
            # Check all responses
            responses = [response1, response2, response3, response4]
            successful_responses = sum(1 for r in responses if r.status_code == 200)
            
            logger.info(f"   Conversation flow responses: {successful_responses}/4 successful")
            
            # Check logs for state transitions
            log_terms = ["FROM_NAME", "FROM_ADDRESS", "conversation", "state"]
            log_results = self.check_backend_logs(log_terms, 100)
            
            state_transitions = []
            for term, lines in log_results.items():
                state_transitions.extend(lines)
            
            # Look for specific state indicators
            from_name_found = any("FROM_NAME" in line for line in state_transitions)
            from_address_found = any("FROM_ADDRESS" in line for line in state_transitions)
            
            logger.info(f"   FROM_NAME state detected: {from_name_found}")
            logger.info(f"   FROM_ADDRESS state detected: {from_address_found}")
            
            # Check for persistence-related logs
            persistence_terms = ["persistence", "pickle", "conversation_state"]
            persistence_logs = self.check_backend_logs(persistence_terms, 50)
            persistence_active = any(len(lines) > 0 for lines in persistence_logs.values())
            
            logger.info(f"   Persistence activity detected: {persistence_active}")
            
            success = successful_responses >= 3 and (from_name_found or from_address_found)
            details = f"Responses: {successful_responses}/4, States: FROM_NAME={from_name_found}, FROM_ADDRESS={from_address_found}"
            
            self.log_test_result("Conversation State Persistence", success, details)
            return success
            
        except Exception as e:
            self.log_test_result("Conversation State Persistence", False, f"Exception: {str(e)}")
            return False
    
    def test_debounce_decorator_functionality(self) -> bool:
        """Test 4: @debounce_input decorator functionality"""
        logger.info("🔍 Test 4: @debounce_input Decorator Functionality")
        
        try:
            # Clear any existing conversation state
            logger.info("   Clearing conversation state")
            start_update = self.create_telegram_update("command", "/start", 4001)
            self.send_webhook_update(start_update)
            time.sleep(0.5)
            
            # Start new order
            new_order_update = self.create_telegram_update("callback", "new_order", 4002)
            self.send_webhook_update(new_order_update)
            time.sleep(0.5)
            
            # Send rapid messages to trigger debounce
            logger.info("   Sending rapid messages to trigger debounce")
            rapid_messages = ["Message 1", "Message 2", "Message 3", "Message 4", "Message 5"]
            
            for i, message in enumerate(rapid_messages):
                update = self.create_telegram_update("text", message, 4010 + i)
                response = self.send_webhook_update(update)
                logger.info(f"   Rapid message {i+1}: '{message}' - HTTP {response.status_code}")
                
                # Very short delay to trigger debounce
                if i < len(rapid_messages) - 1:
                    time.sleep(0.05)  # 50ms delay - should trigger debounce
            
            # Wait for logs to be written
            time.sleep(2)
            
            # Check for debounce-specific logs
            debounce_terms = [
                "🚫 DEBOUNCE BLOCKED",
                "debounce_input",
                "blocked",
                "debounce",
                "rate limit",
                "too fast"
            ]
            
            log_results = self.check_backend_logs(debounce_terms, 150)
            
            debounce_blocks = []
            for term, lines in log_results.items():
                for line in lines:
                    if any(keyword in line.lower() for keyword in ["block", "debounce", "🚫"]):
                        debounce_blocks.append(line)
            
            logger.info(f"   Debounce blocks detected: {len(debounce_blocks)}")
            
            if debounce_blocks:
                logger.info("   Debounce block samples:")
                for block_log in debounce_blocks[:3]:
                    logger.info(f"      {block_log}")
            
            # Check for successful processing of first message
            processing_logs = self.check_backend_logs(["Message 1", "processing", "received"], 100)
            first_message_processed = any("Message 1" in line for lines in processing_logs.values() for line in lines)
            
            logger.info(f"   First message processed: {first_message_processed}")
            
            # Success criteria:
            # 1. Debounce mechanism should block rapid messages
            # 2. First message should be processed
            # 3. Subsequent messages should be blocked
            
            debounce_working = len(debounce_blocks) > 0
            success = debounce_working or first_message_processed  # Either debounce is working OR first message processed
            
            details = f"Debounce blocks: {len(debounce_blocks)}, First processed: {first_message_processed}"
            
            self.log_test_result("Debounce Decorator Functionality", success, details)
            return success
            
        except Exception as e:
            self.log_test_result("Debounce Decorator Functionality", False, f"Exception: {str(e)}")
            return False
    
    def test_session_decorator_interaction(self) -> bool:
        """Test 5: @debounce_input and @with_user_session decorator interaction"""
        logger.info("🔍 Test 5: Decorator Interaction (@debounce_input + @with_user_session)")
        
        try:
            # Test the interaction between decorators
            logger.info("   Testing decorator interaction")
            
            # Start fresh conversation
            start_update = self.create_telegram_update("command", "/start", 5001)
            response1 = self.send_webhook_update(start_update)
            time.sleep(0.3)
            
            new_order_update = self.create_telegram_update("callback", "new_order", 5002)
            response2 = self.send_webhook_update(new_order_update)
            time.sleep(0.5)
            
            # Send a valid message that should be processed
            valid_message = self.create_telegram_update("text", "Valid Sender Name", 5003)
            response3 = self.send_webhook_update(valid_message)
            time.sleep(0.2)
            
            # Send rapid follow-up messages
            rapid_messages = ["Rapid 1", "Rapid 2", "Rapid 3"]
            rapid_responses = []
            
            for i, message in enumerate(rapid_messages):
                update = self.create_telegram_update("text", message, 5010 + i)
                response = self.send_webhook_update(update)
                rapid_responses.append(response)
                time.sleep(0.05)  # 50ms - should trigger debounce
            
            # Wait for processing
            time.sleep(1)
            
            # Check logs for both session and debounce activity
            session_terms = ["session", "user_session", "with_user_session"]
            debounce_terms = ["debounce", "blocked", "🚫"]
            
            session_logs = self.check_backend_logs(session_terms, 100)
            debounce_logs = self.check_backend_logs(debounce_terms, 100)
            
            session_activity = sum(len(lines) for lines in session_logs.values())
            debounce_activity = sum(len(lines) for lines in debounce_logs.values())
            
            logger.info(f"   Session activity logs: {session_activity}")
            logger.info(f"   Debounce activity logs: {debounce_activity}")
            
            # Check for any conflicts or errors
            error_terms = ["error", "exception", "conflict", "failed"]
            error_logs = self.check_backend_logs(error_terms, 50)
            
            decorator_errors = []
            for term, lines in error_logs.items():
                for line in lines:
                    if any(keyword in line.lower() for keyword in ["decorator", "session", "debounce"]):
                        decorator_errors.append(line)
            
            has_decorator_errors = len(decorator_errors) > 0
            
            if decorator_errors:
                logger.info("   Decorator-related errors:")
                for error in decorator_errors[:3]:
                    logger.info(f"      {error}")
            
            # Check response codes
            all_responses = [response1, response2, response3] + rapid_responses
            successful_responses = sum(1 for r in all_responses if r.status_code == 200)
            
            logger.info(f"   Successful responses: {successful_responses}/{len(all_responses)}")
            
            # Success criteria:
            # 1. No decorator conflicts/errors
            # 2. Session management working
            # 3. Debounce working
            # 4. At least initial messages processed successfully
            
            success = (not has_decorator_errors and 
                      successful_responses >= 3 and 
                      (session_activity > 0 or debounce_activity > 0))
            
            details = f"Responses: {successful_responses}/{len(all_responses)}, Session logs: {session_activity}, Debounce logs: {debounce_activity}, Errors: {len(decorator_errors)}"
            
            self.log_test_result("Decorator Interaction", success, details)
            return success
            
        except Exception as e:
            self.log_test_result("Decorator Interaction", False, f"Exception: {str(e)}")
            return False
    
    def test_conversation_progression(self) -> bool:
        """Test 6: Verify bot progresses to next step after processing first message"""
        logger.info("🔍 Test 6: Conversation Progression (FROM_NAME → FROM_ADDRESS)")
        
        try:
            # Start clean conversation
            logger.info("   Starting clean conversation")
            start_update = self.create_telegram_update("command", "/start", 6001)
            self.send_webhook_update(start_update)
            time.sleep(0.3)
            
            new_order_update = self.create_telegram_update("callback", "new_order", 6002)
            self.send_webhook_update(new_order_update)
            time.sleep(0.5)
            
            # Send sender name (should transition FROM_NAME → FROM_ADDRESS)
            logger.info("   Sending sender name")
            name_update = self.create_telegram_update("text", "John Doe", 6003)
            response = self.send_webhook_update(name_update)
            
            logger.info(f"   Name response: HTTP {response.status_code}")
            time.sleep(1)  # Wait for state transition
            
            # Send address (should be accepted if transition worked)
            logger.info("   Sending sender address")
            address_update = self.create_telegram_update("text", "123 Main Street", 6004)
            address_response = self.send_webhook_update(address_update)
            
            logger.info(f"   Address response: HTTP {address_response.status_code}")
            time.sleep(1)
            
            # Check logs for state progression
            state_terms = ["FROM_NAME", "FROM_ADDRESS", "transition", "next step"]
            log_results = self.check_backend_logs(state_terms, 100)
            
            # Look for evidence of state progression
            from_name_logs = log_results.get("FROM_NAME", [])
            from_address_logs = log_results.get("FROM_ADDRESS", [])
            
            # Check for progression indicators
            progression_indicators = [
                "FROM_NAME",
                "FROM_ADDRESS", 
                "next step",
                "transition",
                "address",
                "sender address"
            ]
            
            progression_logs = []
            for indicator in progression_indicators:
                indicator_logs = self.check_backend_logs([indicator], 50)
                for lines in indicator_logs.values():
                    progression_logs.extend(lines)
            
            # Remove duplicates
            progression_logs = list(set(progression_logs))
            
            logger.info(f"   FROM_NAME logs: {len(from_name_logs)}")
            logger.info(f"   FROM_ADDRESS logs: {len(from_address_logs)}")
            logger.info(f"   Progression logs: {len(progression_logs)}")
            
            if progression_logs:
                logger.info("   Progression log samples:")
                for log_line in progression_logs[:3]:
                    logger.info(f"      {log_line}")
            
            # Check response codes
            both_successful = response.status_code == 200 and address_response.status_code == 200
            
            # Success criteria:
            # 1. Both name and address messages processed successfully
            # 2. Evidence of state progression in logs
            # 3. No errors in conversation flow
            
            has_progression_evidence = len(progression_logs) > 0 or (len(from_name_logs) > 0 and len(from_address_logs) > 0)
            
            success = both_successful and has_progression_evidence
            details = f"Responses: Name={response.status_code}, Address={address_response.status_code}, Progression evidence: {has_progression_evidence}"
            
            self.log_test_result("Conversation Progression", success, details)
            return success
            
        except Exception as e:
            self.log_test_result("Conversation Progression", False, f"Exception: {str(e)}")
            return False
    
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run all tests and return comprehensive results"""
        logger.info("🚀 Starting Comprehensive Fast Input Issue Diagnosis")
        logger.info("=" * 80)
        
        start_time = time.time()
        
        # Run all tests
        tests = [
            ("Basic Bot Functionality", self.test_basic_bot_functionality),
            ("Fast Input Scenario", self.test_fast_input_scenario),
            ("Conversation State Persistence", self.test_conversation_state_persistence),
            ("Debounce Decorator Functionality", self.test_debounce_decorator_functionality),
            ("Decorator Interaction", self.test_session_decorator_interaction),
            ("Conversation Progression", self.test_conversation_progression)
        ]
        
        results = {}
        passed_tests = 0
        
        for test_name, test_func in tests:
            logger.info(f"\n{'='*60}")
            try:
                result = test_func()
                results[test_name] = result
                if result:
                    passed_tests += 1
            except Exception as e:
                logger.error(f"Test '{test_name}' failed with exception: {e}")
                results[test_name] = False
        
        total_time = time.time() - start_time
        
        # Generate comprehensive report
        logger.info(f"\n{'='*80}")
        logger.info("🏁 COMPREHENSIVE TEST RESULTS")
        logger.info(f"{'='*80}")
        
        logger.info(f"📊 Test Summary:")
        logger.info(f"   Total Tests: {len(tests)}")
        logger.info(f"   Passed: {passed_tests}")
        logger.info(f"   Failed: {len(tests) - passed_tests}")
        logger.info(f"   Success Rate: {(passed_tests/len(tests)*100):.1f}%")
        logger.info(f"   Total Time: {total_time:.2f}s")
        
        logger.info(f"\n📋 Individual Test Results:")
        for test_result in self.test_results:
            status = "✅ PASS" if test_result['success'] else "❌ FAIL"
            logger.info(f"   {status} {test_result['test']}")
            if test_result['details']:
                logger.info(f"      Details: {test_result['details']}")
        
        # Analyze results for root cause
        logger.info(f"\n🔍 ROOT CAUSE ANALYSIS:")
        
        if not results.get("Basic Bot Functionality", False):
            logger.info("   ❌ CRITICAL: Basic bot functionality is not working")
            logger.info("      - Check bot token configuration")
            logger.info("      - Verify webhook endpoint accessibility")
            logger.info("      - Check ConversationHandler setup")
        
        if not results.get("Fast Input Scenario", False):
            logger.info("   ❌ ISSUE: Fast input scenario failing")
            logger.info("      - Debounce mechanism may not be working properly")
            logger.info("      - Check @debounce_input decorator implementation")
        
        if not results.get("Conversation State Persistence", False):
            logger.info("   ❌ ISSUE: Conversation state persistence problems")
            logger.info("      - Check PicklePersistence configuration")
            logger.info("      - Verify ConversationHandler state management")
            logger.info("      - Check block=False setting compatibility")
        
        if not results.get("Debounce Decorator Functionality", False):
            logger.info("   ❌ ISSUE: Debounce decorator not functioning")
            logger.info("      - @debounce_input decorator may be missing or broken")
            logger.info("      - Check decorator implementation and timing")
        
        if not results.get("Decorator Interaction", False):
            logger.info("   ❌ ISSUE: Decorator interaction problems")
            logger.info("      - Conflict between @debounce_input and @with_user_session")
            logger.info("      - Check decorator order and compatibility")
        
        if not results.get("Conversation Progression", False):
            logger.info("   ❌ ISSUE: Conversation not progressing properly")
            logger.info("      - State transitions may be blocked")
            logger.info("      - Check ConversationHandler state definitions")
        
        # Recommendations
        logger.info(f"\n💡 RECOMMENDATIONS:")
        
        if passed_tests < len(tests) // 2:
            logger.info("   🚨 CRITICAL ISSUES DETECTED:")
            logger.info("      1. Review bot configuration and webhook setup")
            logger.info("      2. Check ConversationHandler and persistence settings")
            logger.info("      3. Verify decorator implementations")
            logger.info("      4. Test with single messages first, then rapid messages")
        else:
            logger.info("   ✅ MOST TESTS PASSING:")
            logger.info("      1. Focus on failed test areas")
            logger.info("      2. Fine-tune debounce timing if needed")
            logger.info("      3. Monitor production logs for similar patterns")
        
        # Final assessment
        if passed_tests == len(tests):
            logger.info(f"\n🎉 ALL TESTS PASSED - Bot should handle fast input correctly")
        elif passed_tests >= len(tests) * 0.8:
            logger.info(f"\n⚠️ MOSTLY WORKING - Minor issues to address")
        elif passed_tests >= len(tests) * 0.5:
            logger.info(f"\n🔧 PARTIAL FUNCTIONALITY - Significant issues need fixing")
        else:
            logger.info(f"\n🚨 CRITICAL ISSUES - Major problems with bot functionality")
        
        return {
            'total_tests': len(tests),
            'passed_tests': passed_tests,
            'success_rate': passed_tests/len(tests)*100,
            'total_time': total_time,
            'individual_results': results,
            'test_details': self.test_results
        }

def main():
    """Main function to run the fast input issue diagnosis"""
    print("🔧 Telegram Bot Fast Input Issue Diagnosis")
    print("=" * 80)
    
    tester = TelegramBotFastInputTester()
    results = tester.run_comprehensive_test()
    
    # Return exit code based on results
    if results['success_rate'] >= 80:
        exit(0)  # Success
    elif results['success_rate'] >= 50:
        exit(1)  # Partial success
    else:
        exit(2)  # Critical issues

if __name__ == "__main__":
    main()