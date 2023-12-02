from django.shortcuts import render
from django.views.generic import ListView, View, DetailView
from requests import request

from furniturepage.forms import CouponForm
from .models import *
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from .forms import CheckoutForm, CouponForm, RefundForm
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from decimal import Decimal
from paypal.standard.forms import PayPalPaymentsForm



# Create your views here.
class HomeView(ListView):
    template_name = "index.html"
    context_object_name = 'items'

    def get_queryset(self):
        return Item.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            try:
                order = Order.objects.get(user=self.request.user, ordered=False)
                context['object'] = order
            except ObjectDoesNotExist:
                messages.error(self.request, "You do not have an active order")
        return context


class ShopView(ListView):
    model = Item
    paginate_by = 6
    template_name = "shop.html"
    context_object_name = 'items'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            try:
                order = Order.objects.get(user=self.request.user, ordered=False)
                context['object'] = order
            except ObjectDoesNotExist:
                messages.error(self.request, "You do not have an active order")
        return context



class CategoryView(View):
    def get(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            try:
                category = Category.objects.get(slug=self.kwargs['slug'])
                item = Item.objects.filter(category=category, is_active=True)
                order = Order.objects.get(user=self.request.user, ordered=False)
                context = {
                    'object': order,
                    'object_list': item,
                    'category_title': category,
                    'category_description': category.description,
                    'category_image': category.image
                }
                return render(self.request, "category.html", context)
            except ObjectDoesNotExist:
                category = Category.objects.get(slug=self.kwargs['slug'])
                item = Item.objects.filter(category=category, is_active=True)
                context = {
                    'object_list': item,
                    'category_title': category,
                    'category_description': category.description,
                    'category_image': category.image
                }
                return render(self.request, "category.html", context)
        else:
            category = Category.objects.get(slug=self.kwargs['slug'])
            item = Item.objects.filter(category=category, is_active=True)
            context = {
                    'object_list': item,
                    'category_title': category,
                    'category_description': category.description,
                    'category_image': category.image
            }
            return render(self.request, "category.html", context)

class ItemDetailView(DetailView):
    model = Item
    template_name = "product-detail.html"



@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(
        item=item,
        user=request.user,
        ordered=False
    )
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "Item qty was updated.")
            return redirect("furniturepage:order-summary")
        else:
            order.items.add(order_item)
            messages.info(request, "Item was added to your cart.")
            return redirect("furniturepage:order-summary")
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, "Item was added to your cart.")
    return redirect("furniturepage:order-summary")


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            order.items.remove(order_item)
            messages.info(request, "Item was removed from your cart.")
            return redirect("furniturepage:order-summary")
        else:
            # add a message saying the user dosent have an order
            messages.info(request, "Item was not in your cart.")
            return redirect("furniturepage:product", slug=slug)
    else:
        # add a message saying the user dosent have an order
        messages.info(request, "u don't have an active order.")
        return redirect("furniturepage:product", slug=slug)
    return redirect("furniturepage:product", slug=slug)


@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order.items.remove(order_item)
            messages.info(request, "This item qty was updated.")
            return redirect("furniturepage:order-summary")
        else:
            # add a message saying the user dosent have an order
            messages.info(request, "Item was not in your cart.")
            return redirect("furniturepage:product", slug=slug)
    else:
        # add a message saying the user dosent have an order
        messages.info(request, "u don't have an active order.")
        return redirect("furniturepage:product", slug=slug)
    return redirect("furniturepage:product", slug=slug)


def get_coupon(request, code):
    try:
        coupon = Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        messages.info(request, "This coupon does not exist")
        return redirect("furniturepage:checkout")


class AddCouponView(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = Order.objects.get(
                    user=self.request.user, ordered=False)
                order.coupon = get_coupon(self.request, code)
                order.save()
                messages.success(self.request, "Successfully added coupon")
                return redirect("furniturepage:checkout")

            except ObjectDoesNotExist:
                return redirect("furniturepage:checkout")

class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'object': order
            }
            return render(self.request, 'order_summary.html', context)
        except ObjectDoesNotExist:
            return render(self.request, 'order_summary.html')

import random
import string
import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))



class CheckoutView(View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            form = CheckoutForm()
            context = {
                'form': form,
                'couponform': CouponForm(),
                'order': order,
                'DISPLAY_COUPON_FORM': True
            }
            return render(self.request, "checkout.html", context)

        except ObjectDoesNotExist:
            messages.info(self.request, "You do not have an active order")
            return redirect("furniturepage:checkout")
    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST)
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            print(self.request.POST)
            if form.is_valid():
                street_address = form.cleaned_data.get('street_address')
                apartment_address = form.cleaned_data.get('apartment_address')
                country = form.cleaned_data.get('country')
                zip = form.cleaned_data.get('zip')

                payment_option = form.cleaned_data.get('payment_option')
                billing_address = BillingAddress(
                    user=self.request.user,
                    street_address=street_address,
                    apartment_address=apartment_address,
                    country=country,
                    zip=zip,
                    address_type='B'
                )
                billing_address.save()
                order.billing_address = billing_address
                order.save()

                # add redirect to the selected payment option
                if payment_option == 'S':
                    return redirect('furniturepage:payment', payment_option='stripe')
                elif payment_option == 'P':
                    return redirect('furniturepage:process_payment', payment_option='paypal')
            else:
                messages.warning(
                        self.request, "Invalid payment option select")
                return redirect("/checkout/")
        except ObjectDoesNotExist:
            messages.error(self.request, "You do not have an active order")
            return redirect("/")

class PaymentView(View):
    def get(self, *args, **kwargs):
        # order
        order = Order.objects.get(user=self.request.user, ordered=False)
        if order.billing_address:
            context = {
                'order': order,
                'DISPLAY_COUPON_FORM': False
            }
            return render(self.request, "payment.html", context)
        else:
            messages.warning(
                self.request, "u have not added a billing address")
            return redirect("furniturepage:checkout")

    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        token = self.request.POST.get('stripeToken')
        amount = int(order.get_total() * 100)
        try:
            charge = stripe.Charge.create(
                amount=amount,  # cents
                currency="usd",
                source=token
            )
            # create the payment
            payment = Payment()
            payment.stripe_charge_id = charge['id']
            payment.user = self.request.user
            payment.amount = order.get_total()
            payment.save()

            # assign the payment to the order
            order.ordered = True
            order.payment = payment
            # TODO : assign ref code
            order.ref_code = create_ref_code()
            order.save()

            messages.success(self.request, "Order was successful")
            return redirect("/")

        except stripe.error.CardError as e:
            # Since it's a decline, stripe.error.CardError will be caught
            body = e.json_body
            err = body.get('error', {})
            messages.error(self.request, f"{err.get('message')}")
            return redirect("/")

        except stripe.error.RateLimitError as e:
            # Too many requests made to the API too quickly
            messages.error(self.request, "RateLimitError")
            return redirect("/")

        except stripe.error.InvalidRequestError as e:
            # Invalid parameters were supplied to Stripe's API
            messages.error(self.request, "The card was declined.")
            return redirect("/")

        except stripe.error.AuthenticationError as e:
            # Authentication with Stripe's API failed
            # (maybe you changed API keys recently)
            messages.error(self.request, "Not Authentication")
            return redirect("/")

        except stripe.error.APIConnectionError as e:
            # Network communication with Stripe failed
            messages.error(self.request, "Network Error")
            return redirect("/")

        except stripe.error.StripeError as e:
            # Display a very generic error to the user, and maybe send
            # yourself an email
            messages.error(self.request, "Something went wrong")
            return redirect("/")

        except Exception as e:
            # send an email to ourselves
            messages.error(self.request, "Serious Error occured")
            return redirect("/")

class PaypalView(View):
    def get(self, *args, **kwargs):
        # order
        order = Order.objects.get(user=self.request.user, ordered=False)
        if order.billing_address:
            context = {
                'order': order,
                'DISPLAY_COUPON_FORM': False
            }
            return render(self.request, 'process_payment.html', context)
        else:
            messages.warning(
                self.request, "u have not added a billing address")
            return redirect("furniturepage:checkout")


@csrf_exempt
def payment_done(request):

    return render(request, 'payment_done.html')

@csrf_exempt
def payment_canceled(request):
    return render(request, 'payment_cancelled.html')


class Contact(View):
    def get(self, request):
        return render(request, 'conctact.html')

class Privacy(View):
    def get(self, request):
        return render(request, 'privacyandterms.html')
