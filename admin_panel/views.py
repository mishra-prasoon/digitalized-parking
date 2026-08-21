from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib import messages
from functools import wraps

from django.http import JsonResponse
import json



def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('is_admin'):
            return redirect('/admin-panel/login/')
        return view_func(request, *args, **kwargs)
    return wrapper

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user and user.is_staff:
            request.session['is_admin'] = True
            request.session['admin_username'] = user.username
            return redirect('/admin-panel/')
        else:
            messages.error(request, 'Invalid credentials or not an admin account')
    return render(request, 'admin_panel/login.html')

def logout_view(request):
    request.session.flush()
    return redirect('/admin-panel/login/')

@admin_required
def dashboard(request):
    return render(request, 'admin_panel/dashboard.html')

@admin_required
def slots_view(request):
    return render(request, 'admin_panel/slots.html')

@admin_required
def transactions_view(request):
    return render(request, 'admin_panel/transactions.html')

@admin_required
def reports_view(request):
    return render(request, 'admin_panel/reports.html')

@admin_required
def gate_control(request):
    return render(request, 'admin_panel/gate_control.html')

@admin_required
def override_slot(request, slot_id):
    from django.http import JsonResponse
    import json
    try:
        from slots.models import ParkingSlot
        slot = ParkingSlot.objects.get(slot_id=slot_id)

        try:
            data = json.loads(request.body)
            action = data.get('action')
        except:
            action = request.POST.get('action')

        if action == 'free':
            slot.is_occupied = False
            slot.save()
        elif action == 'deactivate':
            slot.is_active = False
            slot.save()
        elif action == 'activate':
            slot.is_active = True
            slot.save()
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)

        return JsonResponse({
            'success': True,
            'message': f'Slot {slot_id} updated — {action}'
        })
    except ParkingSlot.DoesNotExist:
        return JsonResponse({'error': 'Slot not found'}, status=404)

@admin_required
def add_slot(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            slot_id = data.get('slot_id', '').upper().strip()
            zone_name = data.get('zone_name', '').strip()
            slot_type = data.get('slot_type', 'Compact')

            if not slot_id or not zone_name:
                return JsonResponse({'error': 'Slot ID and Zone Name are required'}, status=400)

            from slots.models import ParkingSlot
            if ParkingSlot.objects.filter(slot_id=slot_id).exists():
                return JsonResponse({'error': f'Slot {slot_id} already exists'}, status=400)

            slot = ParkingSlot.objects.create(
                slot_id=slot_id,
                zone_name=zone_name,
                slot_type=slot_type,
                is_occupied=False,
                is_active=True,
                status='available'
            )
            return JsonResponse({
                'success': True,
                'message': f'Slot {slot_id} added successfully'
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@admin_required
def delete_slot(request, slot_id):
    if request.method == 'POST':
        try:
            from slots.models import ParkingSlot
            slot = ParkingSlot.objects.get(slot_id=slot_id)

            if slot.is_occupied:
                return JsonResponse({
                    'error': 'Cannot delete an occupied slot'
                }, status=400)

            # Check active transactions
            from transactions.models import Transaction
            active = Transaction.objects.filter(
                slot=slot,
                exit_time__isnull=True
            ).exists()

            if active:
                return JsonResponse({
                    'error': 'Cannot delete slot with active transactions'
                }, status=400)

            slot_id_str = slot.slot_id
            slot.delete()
            return JsonResponse({
                'success': True,
                'message': f'Slot {slot_id_str} deleted successfully'
            })
        except ParkingSlot.DoesNotExist:
            return JsonResponse({'error': 'Slot not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)