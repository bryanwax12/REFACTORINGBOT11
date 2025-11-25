"""
Test thank you message generation with emojis
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, '/app/backend')

async def test_thank_you_generation():
    """Test the thank you message generation"""
    from utils.telegram_utils import generate_thank_you_message, get_random_emojis
    
    print("🧪 Testing Thank You Message Generation\n")
    print("=" * 70)
    
    # Test emoji generation
    print("\n1️⃣ Testing emoji generation (should be different each time):")
    for i in range(5):
        left, right = get_random_emojis()
        print(f"   Attempt {i+1}: {left} ... {right}")
    
    print("\n" + "=" * 70)
    
    # Test full message generation
    print("\n2️⃣ Testing full thank you message generation:")
    print("\nGenerating 3 thank you messages...\n")
    
    for i in range(3):
        try:
            message = await generate_thank_you_message()
            print(f"Message {i+1}:")
            print(f"   {message}")
            print()
        except Exception as e:
            print(f"❌ Error: {e}")
            print()
    
    print("=" * 70)
    print("\n✅ Test completed!\n")
    print("📝 Notes:")
    print("   - Each message should have emojis on both sides")
    print("   - Emojis should be different between messages")
    print("   - Text should mention 'сервис' not 'доставка'")

if __name__ == "__main__":
    asyncio.run(test_thank_you_generation())
