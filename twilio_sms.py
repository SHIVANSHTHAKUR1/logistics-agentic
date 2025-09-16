from twilio.rest import Client
import os

# Your Account SID and Auth Token from twilio.com/console
# Set these as environment variables for security
account_sid = os.getenv('TWILIO_ACCOUNT_SID', 'YOUR_TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN', 'YOUR_TWILIO_AUTH_TOKEN')

# Create Twilio client
client = Client(account_sid, auth_token)

def send_sms(to_number, from_number, message):
    """Send SMS using Twilio"""
    try:
        message = client.messages.create(
            body=message,
            from_=from_number,  # Your Twilio phone number
            to=to_number        # Recipient's phone number
        )
        print(f"Message sent successfully! SID: {message.sid}")
        return message.sid
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

# Example usage
if __name__ == "__main__":
    # Replace with actual phone numbers
    to_phone = "+14155238886"
    from_phone = "+17606062716"  # Your Twilio number
    message_text = "Hello from Twilio!"
    
    send_sms(to_phone, from_phone, message_text)