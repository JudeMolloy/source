import os
import stripe
import traceback

from app import app
from app.routes import is_company
from flask import render_template, url_for, flash, request, session
from werkzeug.utils import redirect
from app.models.payment_link import PaymentLink
from app.models.user import User
from flask_login import current_user, login_required

PRODUCTION = os.environ.get('PRODUCTION')

STRIPE_STANDARD_MONTHLY_PLAN_PRICE_ID = os.environ.get('STRIPE_STANDARD_MONTHLY_PLAN_PRICE_ID')
STRIPE_STANDARD_ANNUAL_PLAN_PRICE_ID = os.environ.get('STRIPE_STANDARD_ANNUAL_PLAN_PRICE_ID')

STRIPE_STANDARD_MONTHLY_PLAN_PRODUCT_ID = os.environ.get('STRIPE_STANDARD_MONTHLY_PLAN_PRODUCT_ID')
STRIPE_STANDARD_ANNUAL_PLAN_PRODUCT_ID = os.environ.get('STRIPE_STANDARD_ANNUAL_PLAN_PRODUCT_ID')

stripe.api_key = os.environ.get('STRIPE_API_KEY')

@app.route('/select-plan')


@app.route('/subscribe')
def subscribe():

    # set the price id for selected plan
    plan = request.args.get('plan')
    if plan == 'standard-monthly':
        price_id = STRIPE_STANDARD_MONTHLY_PLAN_PRICE_ID
        plan = {
            'description': 'Mastero standard monthly plan',
            'monthly_price': 99,
            'billing_schedule': '',
        }
    elif plan == 'standard-annual':
        price_id = STRIPE_STANDARD_ANNUAL_PLAN_PRICE_ID
        plan = {
            'description': 'Mastero standard annual plan',
            'monthly_price': 89,
            'billing_schedule': ' billed annually (89 x 12 = £1068).',
        }
    else:
        return render_template('errors/500.html')

    try:
        # Create a new customer object
        customer = stripe.Customer.create(
            email=current_user.email
        )

        # store customer id for current user
        current_user.stripe_customer_id = customer.id

    except Exception as e:
        print(e.user_message)
        return render_template('errors/500.html')

    try:
        # Create the subscription. Note we're expanding the Subscription's
        # latest invoice and that invoice's payment_intent
        # so we can pass it to the front end to confirm the payment
        subscription = stripe.Subscription.create(
            customer=current_user.stripe_customer_id,
            items=[{
                'price': price_id,
            }],
            payment_behavior='default_incomplete',
            expand=['latest_invoice.payment_intent'],
        )
        return jsonify(subscriptionId=subscription.id, clientSecret=subscription.latest_invoice.payment_intent.client_secret)

    except Exception as e:
        print(e.user_message)
        return render_template('errors/500.html')


@app.route('/connect-with-stripe')
@login_required
def connect_with_stripe():
    # Add a check here to redirect if stripe already connected.

    refresh = request.args.get('refresh')

    try:
        account = stripe.Account.create(
            type='standard',
            email=current_user.email,
        )
        print(account)
        print("THIS IS THE ACCOUNT ID: {}".format(account.id))
        user = User.find_by_id(current_user.id)
        user.stripe_connected_account_id = account.id
        user.save_to_db()
        if PRODUCTION!=1:
            return redirect(url_for('index'))
        if account:
            account_link = stripe.AccountLink.create(
                account=account.id,
                refresh_url='http://localhost:5000/connect-with-stripe?refresh=true',
                return_url='http://localhost:5000/stripe-connect-return',
                type='account_onboarding',
            )
            print(account_link)
            return render_template('payments/connect-with-stripe.html', account_link=account_link, refresh=refresh)
    except:
        traceback.print_exc()
        print("stripe connect failed.")

    return render_template('payments/connect-with-stripe.html', account_link=None)


@app.route('/stripe-connect-return')
def stripe_connect_return():
    # check details submitted and charges enabled. also maybe the
    # check card_payments is active.

    account = stripe.Account.retrieve('acct_1JXCTwDIRb4p7Jz9')

    #account = stripe.Account.retrieve(current_user.stripe_connected_account_id)
    print(account)
    return account



@app.route('/<company_endpoint>/<payment_link_id>/checkout')
def checkout(company_endpoint, payment_link_id):
    company = is_company(company_endpoint)
    if company:

        payment_link = PaymentLink.query.filter_by(company_id=company.id, id=payment_link_id).first_or_404()
        stripe_connected_account_id = User.query.filter_by(company_id=company.id).first_or_404().stripe_connected_account_id

        intent = stripe.PaymentIntent.create(
            payment_method_types=['card'],
            amount=1099,
            currency='gbp',
            # ADD THIS WHEN STRIPE ACCOUNT HAS BEEN CONNECTED stripe_account='{{CONNECTED_STRIPE_ACCOUNT_ID}}',
            stripe_account=stripe_connected_account_id,
            # Verify your integration in this guide by including this parameter
            metadata={'integration_check': 'accept_a_payment'},
        )

        return render_template('payments/checkout.html', client_secret=intent.client_secret, company=company, payment_link=payment_link)
    return render_template("errors/404.html")


@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    # You can use webhooks to receive information about asynchronous payment events.
    # For more about our webhook events check out https://stripe.com/docs/webhooks.
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    request_data = json.loads(request.data)

    if webhook_secret:
        # Retrieve the event by verifying the signature using the raw body and secret if webhook signing is configured.
        signature = request.headers.get('stripe-signature')
        try:
            event = stripe.Webhook.construct_event(
                payload=request.data, sig_header=signature, secret=webhook_secret)
            data = event['data']
        except Exception as e:
            return e
        # Get the type of webhook event sent - used to check the status of PaymentIntents.
        event_type = event['type']
    else:
        data = request_data['data']
        event_type = request_data['type']

    data_object = data['object']
    print(data_object)
    print("TESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTESTTEST")

    if event_type == 'invoice.payment_succeeded':
        if data_object['billing_reason'] == 'subscription_create':
            subscription_id = data_object['subscription']
            payment_intent_id = data_object['payment_intent']

            # Retrieve the payment intent used to pay the subscription
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            # Set the default payment method
            stripe.Subscription.modify(
            subscription_id,
            default_payment_method=payment_intent.payment_method
            )

            status = data_object['status']
            print(status)

            if status == 'active':
                print(subscription_id)
                user = User.find_by_stripe_subscription_id(subscription_id)
                if user:
                    # May want to send an onboarding email here
                    product_id = data_object['items']['data']['price']['product']
                    if product_id == STRIPE_STANDARD_ANNUAL_PLAN_PRODUCT_ID:
                        user.update_subscription(term='annually')
                    elif product_id == STRIPE_STANDARD_MONTHLY_PLAN_PRODUCT_ID:
                        user.update_subscription(term='monthly')
                    else:
                        print("Cannot find associated product id.")

        if data_object['billing_reason'] == 'subscription_cycle':
            subscription_id = data_object['subscription']

            status = data_object['status']
            print(status)

            if status == 'active':
                print(subscription_id)
                user = User.find_by_stripe_subscription_id(subscription_id)
                if user:
                    # May want to send an onboarding email here
                    product_id = data_object['items']['data']['price']['product']
                    if product_id == STRIPE_STANDARD_ANNUAL_PLAN_PRODUCT_ID:
                        user.update_subscription(term='annually')
                    elif product_id == STRIPE_STANDARD_MONTHLY_PLAN_PRODUCT_ID:
                        user.update_subscription(term='monthly')
                    else:
                        print("Cannot find associated product id.")

    if event_type == 'invoice.paid':
        # Used to provision services after the trial has ended.
        # The status of the invoice will show up as paid. Store the status in your
        # database to reference when a user accesses your service to avoid hitting rate
        # limits.
        print(data)

    if event_type == 'invoice.payment_failed':
        # If the payment fails or the customer does not have a valid payment method,
        # an invoice.payment_failed event is sent, the subscription becomes past_due.
        # Use this webhook to notify your user that their payment has
        # failed and to retrieve new card details.
        subscription_id = data_object['subscription']
        user = User.find_by_stripe_subscription_id(subscription_id)
        if user:
            # May want to send an payment failed email here and ask to pay again
            # I will still restrict account access
            user.end_subscription()
            
        print(data)

    if event_type == 'customer.subscription.deleted':
        # handle subscription cancelled automatically based
        # upon your subscription settings. Or if the user cancels it.
        print(data)

    return jsonify({'status': 'success'})