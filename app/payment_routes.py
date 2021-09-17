import os
import stripe
import traceback
import json

from app import app
from app.routes import is_company
from flask import render_template, url_for, flash, request, session, jsonify
from werkzeug.utils import redirect
from app.models.payment_link import PaymentLink
from app.models.user import User
from app.models.request import Request
from app.models.order import Order
from app.models.company import Company
from flask_login import current_user, login_required
from app.forms import BillingInfoForm
from deorators import check_email_confirmed, check_active_subscription

PRODUCTION = os.environ.get('PRODUCTION')

STRIPE_STANDARD_MONTHLY_PLAN_PRICE_ID = os.environ.get('STRIPE_STANDARD_MONTHLY_PLAN_PRICE_ID')
STRIPE_STANDARD_ANNUAL_PLAN_PRICE_ID = os.environ.get('STRIPE_STANDARD_ANNUAL_PLAN_PRICE_ID')

STRIPE_STANDARD_MONTHLY_PLAN_AMOUNT = os.environ.get('STRIPE_STANDARD_MONTHLY_PLAN_AMOUNT')
STRIPE_STANDARD_ANNUAL_PLAN_AMOUNT = os.environ.get('STRIPE_STANDARD_ANNUAL_PLAN_AMOUNT')

STRIPE_STANDARD_MONTHLY_PLAN_PRODUCT_ID = os.environ.get('STRIPE_STANDARD_MONTHLY_PLAN_PRODUCT_ID')
STRIPE_STANDARD_ANNUAL_PLAN_PRODUCT_ID = os.environ.get('STRIPE_STANDARD_ANNUAL_PLAN_PRODUCT_ID')

STRIPE_CONNECT_REFRESH_URL = os.environ.get('STRIPE_CONNECT_REFRESH_URL')
STRIPE_CONNECT_RETURN_URL = os.environ.get('STRIPE_CONNECT_RETURN_URL')

stripe.api_key = os.environ.get('STRIPE_API_KEY')

@app.route('/select-plan')
@login_required
@check_email_confirmed
def select_plan():
    if current_user.active_membership:
        company = Company.query.filter_by(id=current_user.company_id).first()
        if company:
            return redirect(url_for('company_dashboard', company_endpoint=company.endpoint))
        else:
            return redirect(url_for('create_company'))
    return render_template('payments/select-plan.html')


@app.route('/<company_endpoint>/<payment_link_id>/<payment_type>/billing-info',  methods = ['GET', 'POST'])
def billing_info(company_endpoint, payment_link_id, payment_type):
    company = is_company(company_endpoint)
    if company:

        form = BillingInfoForm()
        payment_link = PaymentLink.query.filter_by(company_id=company.id, id=payment_link_id).first_or_404()
        request = Request.query.filter_by(payment_link=payment_link).first_or_404()

        form.full_name.data = payment_link.customer_full_name
        form.email.data = request.email

        if form.validate_on_submit():

            order = Order(
                full_name=form.full_name.data,
                email=form.email.data,
                address1=form.address1.data,
                address2=form.address2.data,
                city=form.city.data,
                country=form.country.data,
                postcode=form.postcode.data,
                payment_type = payment_type,
                company_id=company.id,
                payment_link_id=payment_link.id,
                )
            if payment_type == 'online':
                order.payment_amount = payment_link.price
                submit_button = 'Pay Online'
            elif payment_type == 'deposit':
                order.payment_amount = payment_link.price * (payment_link.deposit_percentage / 100)
                submit_button = 'Pay Deposit'
            else:
                submit_button = 'Complete'
            
            order.save_to_db()
            print(order)

            if order.payment_amount:
                # go to checkout
                return redirect(url_for('checkout', company_endpoint=company_endpoint, payment_link_id=payment_link_id, order_id=order.id))

            return render_template("payments/order-complete.html", company=company, order=order)
            
        return render_template("payments/billing-info.html", form=form, company=company)
    return render_template('errors/500.html')



@app.route('/<company_endpoint>/<payment_link_id>/decline-offer')
def decline_offer(company_endpoint, payment_link_id):
    company = is_company(company_endpoint)
    if company:

        payment_link = PaymentLink.query.filter_by(company_id=company.id, id=payment_link_id).first_or_404()
        payment_link.decline_offer()
        payment_link.save_to_db()
            
        return render_template("offer-declined.html")
    return render_template('errors/500.html')


@app.route('/subscribe')
@login_required
@check_email_confirmed
def subscribe():
    if current_user.active_membership:
        return redirect('index')

    # set the price id for selected plan
    plan = request.args.get('plan')
    if plan == 'standard-monthly':
        price_id = STRIPE_STANDARD_MONTHLY_PLAN_PRICE_ID
        plan = {
            'description': 'Mastero Standard monthly plan',
            'monthly_price': 99,
            'billing_schedule': '',
        }
    elif plan == 'standard-annually':
        price_id = STRIPE_STANDARD_ANNUAL_PLAN_PRICE_ID
        plan = {
            'description': 'Mastero Standard annual plan',
            'monthly_price': 89,
            'billing_schedule': ' billed annually (89 x 12 = £1068)',
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
        print(e)
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

        # save subscription id to user instance.
        current_user.stripe_subscription_id = subscription.id
        current_user.save_to_db()

        return render_template('payments/subscribe.html', subscriptionId=subscription.id, client_secret=subscription.latest_invoice.payment_intent.client_secret, plan=plan, user=current_user)

    except Exception as e:
        print(e)
        return render_template('errors/500.html')


@app.route('/welcome')
@login_required
@check_email_confirmed
def welcome():
    return render_template('payments/welcome.html')

@app.route('/connect-with-stripe')
@login_required
@check_email_confirmed
def connect_with_stripe():
    # Add a check here to redirect if stripe already connected.
    if current_user.stripe_connect_charges_enabled:
        return redirect(url_for('index'))

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
        if PRODUCTION != "TRUE":
            print("WHY")
            print(PRODUCTION)
            return redirect(url_for('create_company'))
        if account:
            account_link = stripe.AccountLink.create(
                account=account.id,
                refresh_url=STRIPE_CONNECT_REFRESH_URL,
                return_url=STRIPE_CONNECT_RETURN_URL,
                type='account_onboarding'
            )
            print(account_link)
            print("WE HERE")
            return render_template('payments/connect-with-stripe.html', account_link=account_link, refresh=refresh)
    except:
        traceback.print_exc()
        print("stripe connect failed.")

    return render_template('payments/connect-with-stripe.html', account_link=None)


@app.route('/stripe-connect-return')
@login_required
@check_email_confirmed
def stripe_connect_return():
    # check details submitted and charges enabled

    account = stripe.Account.retrieve(current_user.stripe_connected_account_id)
    
    if account:

        if account['details_submitted'] == True:
            current_user.stripe_connect_details_submitted = True

        if account['charges_enabled'] == True:
            current_user.stripe_connect_charges_enabled = True

        current_user.save_to_db()
        return redirect(url_for('create_company'))

    return render_template('errors/500.html')


@app.route('/<company_endpoint>/<payment_link_id>/<order_id>/checkout')
def checkout(company_endpoint, payment_link_id, order_id):
    company = is_company(company_endpoint)
    if company:

        payment_link = PaymentLink.query.filter_by(company_id=company.id, id=payment_link_id).first_or_404()
        
        order = Order.query.filter_by(company_id=company.id, id=order_id).first_or_404()

        stripe_connected_account_id = User.query.filter_by(company_id=company.id).first_or_404().stripe_connected_account_id


        amount = int(order.payment_amount * 100)

        intent = stripe.PaymentIntent.create(
            payment_method_types=['card'],
            amount=amount,
            currency='gbp',
            # ADD THIS WHEN STRIPE ACCOUNT HAS BEEN CONNECTED stripe_account='{{CONNECTED_STRIPE_ACCOUNT_ID}}',
            stripe_account=stripe_connected_account_id,
            # Verify your integration in this guide by including this parameter
            metadata={'integration_check': 'accept_a_payment'},
        )
        print(intent.id)
        order.stripe_payment_intent_id = intent.id
        order.save_to_db()
        return render_template('payments/checkout.html', client_secret=intent.client_secret, company=company, payment_link=payment_link, order=order, stripe_connected_account_id=stripe_connected_account_id)
    return render_template("errors/404.html")


@app.route('/<company_endpoint>/<order_id>/complete')
def order_complete(company_endpoint, order_id):
    company = is_company(company_endpoint)
    if company:
        order = Order.query.filter_by(company_id=company.id, id=order_id).first_or_404()
        return render_template('payments/order-complete.html', company=company, order=order)
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
        print("THIS IS THE SIGNATURE {}".format(signature))
        try:
            event = stripe.Webhook.construct_event(
                payload=request.data, sig_header=signature, secret=webhook_secret)
            data = event['data']
        except Exception as e:
            print(e)
            traceback.print_exc()
            return e
        # Get the type of webhook event sent - used to check the status of PaymentIntents.
        event_type = event['type']
    else:
        data = request_data['data']
        event_type = request_data['type']

    data_object = data['object']

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
            print("status: {}".format(status))

            if status == 'paid':
                print(subscription_id)
                user = User.find_by_stripe_subscription_id(subscription_id)
                print("The user is {}".format(user))
                if user:
                    # May want to send an onboarding email here
                    product_id = data_object['lines'].data[0]['price']['product']
                    
                    if product_id == STRIPE_STANDARD_ANNUAL_PLAN_PRODUCT_ID:
                        user.update_subscription(term='annually')
                        user.save_to_db()
                    elif product_id == STRIPE_STANDARD_MONTHLY_PLAN_PRODUCT_ID:
                        user.update_subscription(term='monthly')
                        user.save_to_db()
                    else:
                        print("Cannot find associated product id.")
                        return {'status': 'failed'}, 500
                    return jsonify({'status': 'success'})

        if data_object['billing_reason'] == 'subscription_cycle':
            subscription_id = data_object['subscription']

            status = data_object['status']
            print("status1: {}".format(status))

            if status == 'paid':
                print(subscription_id)
                user = User.find_by_stripe_subscription_id(subscription_id)
                if user:
                    # May want to send an onboarding email here
                    product_id = data_object['lines'].data[0]['price']['product']
                    
                    if product_id == STRIPE_STANDARD_ANNUAL_PLAN_PRODUCT_ID:
                        user.update_subscription(term='annually')
                        user.save_to_db()
                    elif product_id == STRIPE_STANDARD_MONTHLY_PLAN_PRODUCT_ID:
                        user.update_subscription(term='monthly')
                        user.save_to_db()
                    else:
                        print("Cannot find associated product id.")
                        return {'status': 'failed'}, 500
                    return jsonify({'status': 'success'})


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
            user.save_to_db()
            
        print(data)

    if event_type == 'customer.subscription.deleted':
        # handle subscription cancelled automatically based
        # upon your subscription settings. Or if the user cancels it.
        print(data)
    
    if event_type == "payment_intent.succeeded":
        print("DISTINGUISH THIS ONE: {}".format(data_object))
        print(data_object['description'])
        if "Subscription" in data_object['description']:
            print(data_object['description'])
            return jsonify({'status': 'success'})
        payment_intent_id = data_object['id']
        print("payment intent id: {}".format(payment_intent_id))

        order = Order.find_by_stripe_payment_intent_id(payment_intent_id)

        if order:
            order.customer_paid()
            order.save_to_db()
        else:
            print("Order not found")
            return {'status': 'failed'}, 500

    return jsonify({'status': 'success'})