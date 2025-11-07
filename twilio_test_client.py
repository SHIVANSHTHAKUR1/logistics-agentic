#!/usr/bin/env python3
"""Local Twilio webhook test client

Sends a form-encoded POST to the Twilio inbound endpoint with minimal fields:
- From: sender phone (e.g., +15551234567 or whatsapp:+15551234567)
- Body: message text

Note: For local testing, do NOT set TWILIO_AUTH_TOKEN; the server only validates
signatures when that env var is present.

Usage examples:
  python twilio_test_client.py --body "trip 5" 
  python twilio_test_client.py --body "assign load 9 to trip 5" --from "+919999888877"
  python twilio_test_client.py --body "create load pickup A, dest B" --whatsapp
"""
import argparse
import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080/twilio/inbound", help="Inbound webhook URL")
    parser.add_argument("--from", dest="from_number", default="+15551234567", help="Sender phone number")
    parser.add_argument("--body", required=True, help="Message body text")
    parser.add_argument("--whatsapp", action="store_true", help="Prefix From with whatsapp:")
    args = parser.parse_args()

    from_val = args.from_number
    if args.whatsapp and not from_val.startswith("whatsapp:"):
        from_val = f"whatsapp:{from_val}"

    data = {
        "From": from_val,
        "Body": args.body,
    }
    try:
        resp = requests.post(args.url, data=data, timeout=10)
        print(f"Status: {resp.status_code}")
        print(resp.text)
    except Exception as e:
        print(f"Request failed: {e}")


if __name__ == "__main__":
    main()
