from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import User
from vehicles.models import Vehicle


# ── REGISTER ──────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    username = request.data.get('username', '').strip()
    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password', '')
    phone = request.data.get('phone', '').strip()

    # Field validation
    errors = {}

    if not username:
        errors['username'] = 'Username is required'
    elif User.objects.filter(username=username).exists():
        errors['username'] = 'Username already taken'

    if not email:
        errors['email'] = 'Email is required'
    elif User.objects.filter(email=email).exists():
        errors['email'] = 'Email already registered'

    if not password:
        errors['password'] = 'Password is required'
    else:
        try:
            validate_password(password)
        except ValidationError as e:
            errors['password'] = list(e.messages)

    if errors:
        return Response({'error': errors}, status=400)

    # Create user — create_user() hashes password automatically
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        phone=phone,
        role='user'
    )

    # Log in immediately after registration
    login(request, user)

    return Response({
        'success': True,
        'message': f'Account created successfully! Welcome {username}.',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'phone': user.phone,
            'role': user.role
        }
    }, status=201)


# ── LOGIN ─────────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')

    if not username or not password:
        return Response(
            {'error': 'Username and password are required'}, status=400
        )

    # authenticate() checks password against hash — never compare manually
    user = authenticate(request, username=username, password=password)

    if user is None:
        return Response(
            {'error': 'Invalid username or password'}, status=401
        )

    if not user.is_active:
        return Response(
            {'error': 'Account is disabled. Please contact support.'}, status=401
        )

    # login() creates the session
    login(request, user)

    return Response({
        'success': True,
        'message': f'Welcome back, {user.username}!',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'phone': user.phone,
            'role': user.role,
            'is_staff': user.is_staff
        }
    })


# ── LOGOUT ────────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    logout(request)
    return Response({'success': True, 'message': 'Logged out successfully'})


# ── CURRENT USER ──────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'phone': user.phone,
        'role': user.role,
        'is_staff': user.is_staff
    })


# ── VEHICLES ──────────────────────────────────────────────────────
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def vehicles(request):
    if request.method == 'GET':
        # Return only this user's vehicles
        user_vehicles = Vehicle.objects.filter(registered_user=request.user)
        return Response([{
            'vehicle_no': v.vehicle_no,
            'owner_name': v.owner_name,
            'vehicle_type': v.vehicle_type
        } for v in user_vehicles])

    if request.method == 'POST':
        vehicle_no = request.data.get('vehicle_no', '').upper().strip()
        owner_name = request.data.get('owner_name', '').strip()
        vehicle_type = request.data.get('vehicle_type', 'Compact')

        if not vehicle_no:
            return Response({'error': 'Vehicle number is required'}, status=400)

        if Vehicle.objects.filter(vehicle_no=vehicle_no).exists():
            # If vehicle exists and belongs to this user, return it
            v = Vehicle.objects.get(vehicle_no=vehicle_no)
            if v.registered_user == request.user:
                return Response({
                    'success': True,
                    'message': 'Vehicle already registered to your account',
                    'vehicle_no': v.vehicle_no
                })
            else:
                return Response(
                    {'error': 'This vehicle is registered to another account'},
                    status=400
                )

        vehicle = Vehicle.objects.create(
            vehicle_no=vehicle_no,
            owner_name=owner_name or request.user.get_full_name() or request.user.username,
            vehicle_type=vehicle_type,
            registered_user=request.user  # Always from request.user, never from body
        )

        return Response({
            'success': True,
            'message': f'Vehicle {vehicle_no} registered successfully',
            'vehicle_no': vehicle.vehicle_no,
            'vehicle_type': vehicle.vehicle_type
        }, status=201)
