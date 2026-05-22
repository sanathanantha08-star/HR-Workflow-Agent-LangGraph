"""
Standalone Twilio call test — bypasses the full workflow.
Run: python test_call.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

from twilio.rest import Client

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
from_number = os.getenv("TWILIO_FROM_NUMBER")
to_number   = "+918951523420"
public_url  = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

print(f"Account SID : {account_sid}")
print(f"From        : {from_number}")
print(f"To          : {to_number}")
print(f"Webhook     : {public_url}/api/webhooks/twilio/voice?session_id=test&candidate_name=Sanath")

# Quick webhook reachability check (SSL verification disabled for local test only)
import urllib.request, ssl
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
try:
    urllib.request.urlopen(f"{public_url}/health", timeout=5, context=ctx)
    print("\n✅ ngrok webhook is reachable")
except Exception as e:
    print(f"\n❌ ngrok webhook NOT reachable: {e}")
    print("   → Make sure ngrok is running and PUBLIC_BASE_URL in .env matches the current ngrok URL")
    exit(1)

confirm = input("\nProceed with test call to +918951523420? (y/n): ")
if confirm.lower() != "y":
    exit(0)

client = Client(account_sid, auth_token)
try:
    call = client.calls.create(
        to=to_number,
        from_=from_number,
        url=f"{public_url}/api/webhooks/twilio/ping",
        status_callback=f"{public_url}/api/webhooks/twilio/call-status",
        status_callback_method="POST",
    )
    print(f"\n✅ Call initiated! SID: {call.sid}  Status: {call.status}")
    print("   → You should receive a call on +918951523420 in ~5 seconds")
    print(f"   → Track it: https://console.twilio.com/us1/monitor/logs/calls/{call.sid}")
except Exception as e:
    print(f"\n❌ Twilio call failed: {e}")
