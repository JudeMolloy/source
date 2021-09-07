import os
import stripe
import traceback

from app import app
from app.routes import is_company
from flask import render_template, url_for, flash, request, session
from werkzeug.utils import redirect
from app.models.payment_link import PaymentLink

stripe.api_key = os.environ.get('STRIPE_API_KEY')


@app.route('/connect-with-stripe')
def connect_with_stripe():
    # Add a check here to redirect if stripe already connected.
    try:
        account = stripe.Account.create(
            type='standard',
            email='test@test.com'
        )
        print(account)
        print("THIS IS THE ACCOUNT ID: {}".format(account.id))
        if account:
            account_link = stripe.AccountLink.create(
                account=account.id,
                refresh_url='https://example.com/reauth',
                return_url='https://example.com/return',
                type='account_onboarding',
            )
            print(account_link)
            return render_template('payments/connect-with-stripe.html', account_link=account_link)
    except:
        traceback.print_exc()
        print("stripe connect failed.")

    return render_template('payments/connect-with-stripe.html', account_link=None)

@app.route('/<company_endpoint>/<payment_link_id>/checkout')
def checkout(company_endpoint, payment_link_id):
    company = is_company(company_endpoint)
    if company:

        payment_link = PaymentLink.query.filter_by(company_id=company.id, id=payment_link_id).first_or_404()

        intent = stripe.PaymentIntent.create(
            amount=1099,
            currency='gbp',
            # ADD THIS WHEN STRIPE ACCOUNT HAS BEEN CONNECTED stripe_account='{{CONNECTED_STRIPE_ACCOUNT_ID}}',
            # Verify your integration in this guide by including this parameter
            metadata={'integration_check': 'accept_a_payment'},
        )

        return render_template('payments/checkout.html', client_secret=intent.client_secret, company=company, payment_link=payment_link)
    return render_template("errors/404.html")