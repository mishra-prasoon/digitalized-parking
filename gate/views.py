from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from core.models import Vehicle
from parking.services import allocate_and_check_in, check_out, AllocationError
from parking.models import Transaction
from anpr.pipeline import read_plate_from_bytes, vote_across_frames
from anpr.models import ANPRLog
from payments.services import create_order, verify_and_close, PaymentError


def entry_gate(request):
    if not request.user.is_staff_member:
        raise PermissionDenied
    return render(request, 'gate/entry.html')


@csrf_exempt
def entry_check_in(request):
    if not request.user.is_staff_member:
        raise PermissionDenied
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    manual_plate = request.POST.get('manual_plate', '').strip().upper()
    images = request.FILES.getlist('images')

    plate = None
    confidence = 0
    raw_text = ''

    if manual_plate:
        plate = manual_plate
    elif images:
        results = [read_plate_from_bytes(f.read()) for f in images]
        plate, confidence, raw_text = vote_across_frames(results)
        ANPRLog.objects.create(
            gate=ANPRLog.Gate.ENTRY,
            raw_text=raw_text[:50],
            accepted_plate=plate or '',
            confidence=confidence,
            success=bool(plate),
        )
    else:
        return JsonResponse({'error': 'No images or manual plate provided'}, status=400)

    if not plate:
        return JsonResponse({'plate': None, 'message': 'No plate detected. Enter manually.'}, status=200)

    vehicle, _ = Vehicle.objects.get_or_create(plate=plate)

    try:
        txn = allocate_and_check_in(vehicle)
    except AllocationError as e:
        return JsonResponse({'plate': plate, 'error': str(e)}, status=409)

    return JsonResponse({
        'plate': plate,
        'slot_id': txn.slot_id,
        'entry_time': txn.entry_time.isoformat(),
    })


def exit_gate(request):
    if not request.user.is_staff_member:
        raise PermissionDenied
    return render(request, 'gate/exit.html', {'razorpay_key_id': settings.RAZORPAY_KEY_ID})


@csrf_exempt
def exit_scan(request):
    if not request.user.is_staff_member:
        raise PermissionDenied
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    manual_plate = request.POST.get('manual_plate', '').strip().upper()
    images = request.FILES.getlist('images')

    plate = None
    raw_text = ''
    confidence = 0

    if manual_plate:
        plate = manual_plate
    elif images:
        results = [read_plate_from_bytes(f.read()) for f in images]
        plate, confidence, raw_text = vote_across_frames(results)
        ANPRLog.objects.create(
            gate=ANPRLog.Gate.EXIT,
            raw_text=raw_text[:50],
            accepted_plate=plate or '',
            confidence=confidence,
            success=bool(plate),
        )
    else:
        return JsonResponse({'error': 'No images or manual plate provided'}, status=400)

    if not plate:
        return JsonResponse({'plate': None, 'message': 'No plate detected. Enter manually.'}, status=200)

    try:
        vehicle = Vehicle.objects.get(plate=plate)
        txn = check_out(vehicle)
    except (Vehicle.DoesNotExist, AllocationError) as e:
        return JsonResponse({'plate': plate, 'error': str(e)}, status=409)

    payment, order = create_order(txn)

    return JsonResponse({
        'plate': plate,
        'transaction_id': txn.id,
        'fee': str(txn.fee),
        'razorpay_order_id': order['id'],
        'amount_paise': payment.amount_paise,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
    })


@csrf_exempt
def exit_confirm_payment(request):
    if not request.user.is_staff_member:
        raise PermissionDenied
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    transaction_id = request.POST.get('transaction_id')
    razorpay_order_id = request.POST.get('razorpay_order_id')
    razorpay_payment_id = request.POST.get('razorpay_payment_id')
    razorpay_signature = request.POST.get('razorpay_signature')

    try:
        txn = Transaction.objects.get(pk=transaction_id)
    except Transaction.DoesNotExist:
        return JsonResponse({'error': 'Transaction not found'}, status=404)

    try:
        verify_and_close(txn, razorpay_order_id, razorpay_payment_id, razorpay_signature)
    except PaymentError as e:
        return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'status': 'closed', 'transaction_id': txn.id})
