from twilio.rest import Client
import os

# Your Account SID and Auth Token from twilio.com/console
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

# Create Twilio client
client = Client(account_sid, auth_token)

def _ensure_whatsapp_prefix(number: str) -> str:
    if not number:
        return number
    return number if number.startswith("whatsapp:") else f"whatsapp:{number}"

def send_sms(to_number, from_number, message):
    """Send SMS using Twilio"""
    try:
        msg = client.messages.create(
            body=message,
            from_=from_number,  # Your Twilio phone number
            to=to_number        # Recipient's phone number
        )
        print(f"Message sent successfully! SID: {msg.sid}")
        return msg.sid
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def send_whatsapp(to_number, from_number, message):
    """Send WhatsApp message using Twilio"""
    try:
        msg = client.messages.create(
            body=message,
            from_=_ensure_whatsapp_prefix(from_number),  # e.g., whatsapp:+14155238886 (sandbox) or your WA-enabled number
            to=_ensure_whatsapp_prefix(to_number)        # e.g., whatsapp:+1234567890
        )
        print(f"WhatsApp message sent successfully! SID: {msg.sid}")
        return msg.sid
    except Exception as e:
        print(f"Error sending WhatsApp message: {e}")
        return None

# Example usage
if __name__ == "__main__":
    # Replace with actual phone numbers (E.164 format). Prefixing added automatically.
    to_phone = "+918968808710"
    # Set to your WhatsApp-enabled Twilio number or sandbox number in env
    from_phone = os.getenv('TWILIO_WHATSAPP_NUMBER')  # sandbox default; prefer env

    message_text = "Hello from Twilio WhatsApp!"

    send_whatsapp(to_phone, from_phone, message_text)