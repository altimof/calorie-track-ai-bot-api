#!/usr/bin/env python3
"""
Script to check Telegram bot connection status.
Run this after deploying your app to verify everything is working.
The webhook check needs the app's admin token in the ADMIN_API_TOKEN env var.
"""

import asyncio
import os
import sys

import httpx


async def check_bot_connection(app_url: str, bot_token: str | None = None) -> None:
    """Check if the bot is properly connected to Telegram."""

    print("🔍 Checking Telegram Bot Connection...")
    print("=" * 50)

    # Check 1: App health
    print("1. Checking app health...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{app_url}/healthz")
            if response.status_code == 200:
                print("   ✅ App is running")
            else:
                print(f"   ❌ App health check failed: {response.status_code}")
                return
    except Exception as e:
        print(f"   ❌ Cannot reach app: {e}")
        return

    # Check 2: Bot webhook info
    print("2. Checking webhook status...")
    try:
        async with httpx.AsyncClient() as client:
            admin_token = os.getenv("ADMIN_API_TOKEN")
            headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}
            response = await client.get(f"{app_url}/bot/webhook-info", headers=headers)
            if response.status_code in (401, 404):
                print(
                    "   ⚠️  Skipped: set ADMIN_API_TOKEN to the app's admin token "
                    "(the route is disabled when the app has none)"
                )
            elif response.status_code == 200:
                data = response.json()
                webhook_info = data.get("webhook_info", {})

                if webhook_info.get("url"):
                    print(f"   ✅ Webhook is set: {webhook_info['url']}")

                    if webhook_info.get("last_error_message"):
                        print(f"   ⚠️  Last error: {webhook_info['last_error_message']}")
                    else:
                        print("   ✅ No webhook errors")

                    pending = webhook_info.get("pending_update_count", 0)
                    print(f"   📊 Pending updates: {pending}")
                else:
                    print("   ❌ No webhook URL set")
            else:
                print(f"   ❌ Webhook info check failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error checking webhook: {e}")

    # Check 3: Bot token validity (if provided)
    if bot_token:
        print("3. Checking bot token...")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        bot_info = data["result"]
                        print(
                            f"   ✅ Bot is valid: @{bot_info.get('username')} ({bot_info.get('first_name')})"
                        )
                    else:
                        print(f"   ❌ Bot token invalid: {data.get('description')}")
                else:
                    print(f"   ❌ Bot API error: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error checking bot token: {e}")
    else:
        print("3. Skipping bot token check (not provided)")

    # Check 4: Test webhook endpoint
    print("4. Testing webhook endpoint...")
    try:
        test_payload = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "from": {"id": 12345, "username": "testuser"},
                "chat": {"id": 12345, "type": "private"},
                "date": 1640995200,
                "text": "/start",
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{app_url}/bot", json=test_payload)
            if response.status_code == 200:
                print("   ✅ Webhook endpoint responds correctly")
            else:
                print(f"   ❌ Webhook endpoint error: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error testing webhook: {e}")

    print("\n" + "=" * 50)
    print("🎯 Next steps:")
    print("1. Find your bot on Telegram")
    print("2. Send /start command")
    print("3. Send a photo to test calorie estimation")
    print("4. Check app logs for detailed information")


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python check_bot_connection.py <APP_URL> [BOT_TOKEN]")
        print("Example: python check_bot_connection.py https://your-app.fly.dev")
        print("Example: python check_bot_connection.py https://your-app.fly.dev 123456:ABC-DEF")
        sys.exit(1)

    app_url = sys.argv[1].rstrip("/")
    bot_token = sys.argv[2] if len(sys.argv) > 2 else None

    asyncio.run(check_bot_connection(app_url, bot_token))


if __name__ == "__main__":
    main()
