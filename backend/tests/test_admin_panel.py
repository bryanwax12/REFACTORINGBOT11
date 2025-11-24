"""
Comprehensive Admin Panel API Testing
Tests all admin panel functionality
"""
import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = "http://localhost:8001"
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "sk_admin_e19063c3f82f447ba4ccf49cd97dd9fd_2024")
TEST_USER_ID = 7000000003  # тестовый пользователь для всех операций


class AdminPanelTester:
    def __init__(self):
        self.headers = {"X-API-Key": ADMIN_API_KEY}
        self.results = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "tests": []
        }
    
    def log_test(self, name, passed, message=""):
        """Log test result"""
        status = "✅" if passed else "❌"
        self.results["total_tests"] += 1
        if passed:
            self.results["passed"] += 1
        else:
            self.results["failed"] += 1
        
        self.results["tests"].append({
            "name": name,
            "passed": passed,
            "message": message
        })
        print(f"{status} {name}: {message}")
    
    async def run_all_tests(self):
        """Run all admin panel tests"""
        print("=" * 80)
        print("🧪 ADMIN PANEL COMPREHENSIVE TESTING")
        print("=" * 80)
        print()
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test 1: Get Users List
            await self.test_get_users(client)
            
            # Test 2: Get User Details
            await self.test_get_user_details(client)
            
            # Test 3: Add Balance
            await self.test_add_balance(client)
            
            # Test 4: Deduct Balance
            await self.test_deduct_balance(client)
            
            # Test 5: Block User
            await self.test_block_user(client)
            
            # Test 6: Unblock User
            await self.test_unblock_user(client)
            
            # Test 7: Get Stats
            await self.test_get_stats(client)
            
            # Test 8: Get Topups
            await self.test_get_topups(client)
            
            # Test 9: Maintenance Mode
            await self.test_maintenance_mode(client)
        
        # Print summary
        self.print_summary()
    
    async def test_get_users(self, client):
        """Test GET /api/admin/users"""
        try:
            response = await client.get(
                f"{BACKEND_URL}/api/admin/users",
                headers=self.headers
            )
            
            if response.status_code == 200:
                users = response.json()
                if isinstance(users, list) and len(users) > 0:
                    self.log_test(
                        "Get Users List",
                        True,
                        f"Retrieved {len(users)} users"
                    )
                    return users
                else:
                    self.log_test("Get Users List", False, "Empty user list")
            else:
                self.log_test(
                    "Get Users List",
                    False,
                    f"Status {response.status_code}"
                )
        except Exception as e:
            self.log_test("Get Users List", False, str(e))
        
        return []
    
    async def test_get_user_details(self, client):
        """Test GET /api/admin/users/{telegram_id}/details"""
        try:
            response = await client.get(
                f"{BACKEND_URL}/api/admin/users/{TEST_USER_ID}/details",
                headers=self.headers
            )
            
            if response.status_code == 200:
                details = response.json()
                if "user" in details and "statistics" in details:
                    self.log_test(
                        "Get User Details",
                        True,
                        f"User: {details['user'].get('telegram_id')}, " +
                        f"Balance: ${details['statistics'].get('current_balance', 0)}"
                    )
                    return details
                else:
                    self.log_test("Get User Details", False, "Invalid response format")
            else:
                self.log_test(
                    "Get User Details",
                    False,
                    f"Status {response.status_code}"
                )
        except Exception as e:
            self.log_test("Get User Details", False, str(e))
        
        return None
    
    async def test_add_balance(self, client):
        """Test POST /api/admin/users/{telegram_id}/balance/add"""
        try:
            # Get current balance
            response = await client.get(
                f"{BACKEND_URL}/api/admin/users",
                headers=self.headers
            )
            users = response.json()
            user = next((u for u in users if u.get("telegram_id") == TEST_USER_ID), None)
            old_balance = user.get("balance", 0) if user else 0
            
            # Add balance
            response = await client.post(
                f"{BACKEND_URL}/api/admin/users/{TEST_USER_ID}/balance/add?amount=10",
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success") and result.get("new_balance") == old_balance + 10:
                    self.log_test(
                        "Add Balance",
                        True,
                        f"${old_balance} → ${result.get('new_balance')}"
                    )
                else:
                    self.log_test("Add Balance", False, "Balance not updated correctly")
            else:
                self.log_test("Add Balance", False, f"Status {response.status_code}")
        except Exception as e:
            self.log_test("Add Balance", False, str(e))
    
    async def test_deduct_balance(self, client):
        """Test POST /api/admin/users/{telegram_id}/balance/deduct"""
        try:
            # Get current balance
            response = await client.get(
                f"{BACKEND_URL}/api/admin/users",
                headers=self.headers
            )
            users = response.json()
            user = next((u for u in users if u.get("telegram_id") == TEST_USER_ID), None)
            old_balance = user.get("balance", 0) if user else 0
            
            # Deduct balance
            response = await client.post(
                f"{BACKEND_URL}/api/admin/users/{TEST_USER_ID}/balance/deduct?amount=5",
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success") and result.get("new_balance") == old_balance - 5:
                    self.log_test(
                        "Deduct Balance",
                        True,
                        f"${old_balance} → ${result.get('new_balance')}"
                    )
                else:
                    self.log_test("Deduct Balance", False, "Balance not updated correctly")
            else:
                self.log_test("Deduct Balance", False, f"Status {response.status_code}")
        except Exception as e:
            self.log_test("Deduct Balance", False, str(e))
    
    async def test_block_user(self, client):
        """Test POST /api/admin/users/{telegram_id}/block"""
        try:
            response = await client.post(
                f"{BACKEND_URL}/api/admin/users/{TEST_USER_ID}/block",
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    # Verify blocked status
                    response = await client.get(
                        f"{BACKEND_URL}/api/admin/users",
                        headers=self.headers
                    )
                    users = response.json()
                    user = next((u for u in users if u.get("telegram_id") == TEST_USER_ID), None)
                    
                    if user and user.get("blocked"):
                        self.log_test("Block User", True, "User successfully blocked")
                    else:
                        self.log_test("Block User", False, "Blocked status not updated")
                else:
                    self.log_test("Block User", False, result.get("message", "Unknown error"))
            else:
                self.log_test("Block User", False, f"Status {response.status_code}")
        except Exception as e:
            self.log_test("Block User", False, str(e))
    
    async def test_unblock_user(self, client):
        """Test POST /api/admin/users/{telegram_id}/unblock"""
        try:
            response = await client.post(
                f"{BACKEND_URL}/api/admin/users/{TEST_USER_ID}/unblock",
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    # Verify unblocked status
                    response = await client.get(
                        f"{BACKEND_URL}/api/admin/users",
                        headers=self.headers
                    )
                    users = response.json()
                    user = next((u for u in users if u.get("telegram_id") == TEST_USER_ID), None)
                    
                    if user and not user.get("blocked"):
                        self.log_test("Unblock User", True, "User successfully unblocked")
                    else:
                        self.log_test("Unblock User", False, "Blocked status not updated")
                else:
                    self.log_test("Unblock User", False, result.get("message", "Unknown error"))
            else:
                self.log_test("Unblock User", False, f"Status {response.status_code}")
        except Exception as e:
            self.log_test("Unblock User", False, str(e))
    
    async def test_get_stats(self, client):
        """Test GET /api/admin/stats"""
        try:
            response = await client.get(
                f"{BACKEND_URL}/api/admin/stats",
                headers=self.headers
            )
            
            if response.status_code == 200:
                stats = response.json()
                if "total_users" in stats:
                    self.log_test(
                        "Get Statistics",
                        True,
                        f"Users: {stats.get('total_users')}, " +
                        f"Orders: {stats.get('total_orders')}"
                    )
                else:
                    self.log_test("Get Statistics", False, "Invalid stats format")
            else:
                self.log_test("Get Statistics", False, f"Status {response.status_code}")
        except Exception as e:
            self.log_test("Get Statistics", False, str(e))
    
    async def test_get_topups(self, client):
        """Test GET /api/admin/topups"""
        try:
            response = await client.get(
                f"{BACKEND_URL}/api/admin/topups",
                headers=self.headers
            )
            
            if response.status_code == 200:
                topups = response.json()
                if isinstance(topups, list):
                    self.log_test(
                        "Get Topups",
                        True,
                        f"Retrieved {len(topups)} topup records"
                    )
                else:
                    self.log_test("Get Topups", False, "Invalid response format")
            else:
                self.log_test("Get Topups", False, f"Status {response.status_code}")
        except Exception as e:
            self.log_test("Get Topups", False, str(e))
    
    async def test_maintenance_mode(self, client):
        """Test maintenance mode endpoints"""
        try:
            # Get current status
            response = await client.get(
                f"{BACKEND_URL}/api/admin/maintenance/status",
                headers=self.headers
            )
            
            if response.status_code != 200:
                self.log_test("Maintenance Mode", False, "Failed to get status")
                return
            
            # Enable maintenance mode
            response = await client.post(
                f"{BACKEND_URL}/api/admin/maintenance/enable",
                headers=self.headers
            )
            
            if response.status_code != 200:
                self.log_test("Maintenance Mode", False, "Failed to enable")
                return
            
            # Verify enabled
            response = await client.get(
                f"{BACKEND_URL}/api/admin/maintenance/status",
                headers=self.headers
            )
            result = response.json()
            
            if not result.get("maintenance_mode"):
                self.log_test("Maintenance Mode", False, "Not enabled")
                return
            
            # Disable maintenance mode
            response = await client.post(
                f"{BACKEND_URL}/api/admin/maintenance/disable",
                headers=self.headers
            )
            
            if response.status_code != 200:
                self.log_test("Maintenance Mode", False, "Failed to disable")
                return
            
            self.log_test("Maintenance Mode", True, "Enable/Disable cycle successful")
        
        except Exception as e:
            self.log_test("Maintenance Mode", False, str(e))
    
    def print_summary(self):
        """Print test summary"""
        print()
        print("=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {self.results['total_tests']}")
        print(f"✅ Passed: {self.results['passed']}")
        print(f"❌ Failed: {self.results['failed']}")
        
        if self.results['total_tests'] > 0:
            success_rate = (self.results['passed'] / self.results['total_tests']) * 100
            print(f"📈 Success Rate: {success_rate:.1f}%")
            print()
            
            if success_rate == 100:
                print("🎉 ALL TESTS PASSED! Admin panel is fully functional.")
            elif success_rate >= 80:
                print("✅ Most tests passed. Admin panel is mostly functional.")
            else:
                print("⚠️  Multiple failures detected. Admin panel needs fixes.")
        
        print("=" * 80)


async def main():
    tester = AdminPanelTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
