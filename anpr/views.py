import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import ANPRLog
from .pipeline import read_plate_from_bytes, vote_across_frames


def _check_device_key(request):
    return request.headers.get('X-Device-Key') == settings.DEVICE_API_KEY and bool(settings.DEVICE_API_KEY)


@csrf_exempt
@require_POST
def anpr_read(request, gate):
    if gate not in ('entry', 'exit'):
        return JsonResponse({'error': 'invalid gate'}, status=400)

    if not _check_device_key(request):
        return JsonResponse({'error': 'unauthorized'}, status=401)

    images = request.FILES.getlist('images')
    if not images:
        return JsonResponse({'error': 'no images provided'}, status=400)

    results = [read_plate_from_bytes(f.read()) for f in images]
    plate, confidence, raw_text = vote_across_frames(results)

    ANPRLog.objects.create(
        gate=gate,
        raw_text=raw_text[:50],
        accepted_plate=plate or '',
        confidence=confidence,
        success=bool(plate),
    )

    if plate:
        return JsonResponse({'plate': plate, 'confidence': confidence})
    return JsonResponse({'plate': None, 'message': 'No plate detected with sufficient confidence. Use manual entry.', 'confidence': confidence}, status=200)
