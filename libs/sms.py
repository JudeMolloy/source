import os
import json
from twilio.rest import Client

class Twilio:

    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    NOTIFY_SERVICE_SID = os.environ.get('NOTIFY_SERVICE_SID')

    client = Client(account_sid, auth_token)

    @classmethod
    def send_bulk_sms(cls, numbers, body):
        bindings = list(map(lambda number: json.dumps({'binding_type': 'sms', 'address': number}), numbers))
        notification = cls.client.notify.services(cls.NOTIFY_SERVICE_SID).notifications.create(
            to_binding=bindings,
            body=body
        )

    @classmethod
    def send_sms(cls, message: str, sender: str, phone_number: str):
        try:
            message = cls.client.messages.create(
                                        body=message,
                                        from_=sender,
                                        to=phone_number
                                    )
        except:
            print("Something went wrong...")
