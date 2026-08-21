from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages


def home(request):
    return render(request, 'user/home.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)
        if user and user.is_active:
            login(request, user)
            next_url = request.GET.get('next', '/')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password')

    return render(request, 'user/login.html')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm_password', '')
        phone = request.POST.get('phone', '').strip()
        vehicle_no = request.POST.get('vehicle_no', '').upper().strip()

        # Validation
        from accounts.models import User
        if password != confirm:
            messages.error(request, 'Passwords do not match')
            return render(request, 'user/register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken')
            return render(request, 'user/register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered')
            return render(request, 'user/register.html')

        try:
            from django.contrib.auth.password_validation import validate_password
            from django.core.exceptions import ValidationError
            validate_password(password)
        except ValidationError as e:
            for error in e.messages:
                messages.error(request, error)
            return render(request, 'user/register.html')

        # Create user with hashed password
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            phone=phone,
            role='user'
        )

        # Register vehicle if provided
        if vehicle_no:
            from vehicles.models import Vehicle
            Vehicle.objects.get_or_create(
                vehicle_no=vehicle_no,
                defaults={
                    'owner_name': username,
                    'vehicle_type': 'Compact',
                    'registered_user': user
                }
            )

        login(request, user)
        messages.success(request, f'Welcome {username}! Account created successfully.')
        return redirect('/')

    return render(request, 'user/register.html')


def logout_view(request):
    logout(request)
    return redirect('/login/')


def slots_view(request):
    return render(request, 'user/slots.html')


def book_view(request):
    if not request.user.is_authenticated:
        messages.error(request, 'Please login to book a slot')
        return redirect(f'/login/?next=/book/')
    return render(request, 'user/book.html')


def my_bookings(request):
    if not request.user.is_authenticated:
        return redirect(f'/login/?next=/my-bookings/')
    return render(request, 'user/my_bookings.html')


def payment_view(request):
    return render(request, 'user/payment.html')


def anpr_demo(request):
    return render(request, 'gate/anpr_demo.html')