from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import ParkingSlot
from .serializers import ParkingSlotSerializer

class SlotListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ParkingSlotSerializer

    def get_queryset(self):
        queryset = ParkingSlot.objects.filter(is_active=True)
        zone = self.request.query_params.get('zone')
        slot_type = self.request.query_params.get('slot_type')
        status = self.request.query_params.get('status')
        if zone:
            queryset = queryset.filter(zone_name=zone)
        if slot_type:
            queryset = queryset.filter(slot_type=slot_type)
        if status:
            queryset = queryset.filter(status=status)
        return queryset

@api_view(['GET'])
@permission_classes([AllowAny])
def available_slots(request):
    slots = ParkingSlot.objects.filter(is_active=True, is_occupied=False, status='available')
    serializer = ParkingSlotSerializer(slots, many=True)
    return Response({
        'total_available': slots.count(),
        'slots': serializer.data
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def update_slot_status(request, slot_id):
    try:
        slot = ParkingSlot.objects.get(slot_id=slot_id)
        action = request.data.get('action')
        if action == 'occupy':
            slot.is_occupied = True
        elif action == 'free':
            slot.is_occupied = False
        elif action == 'deactivate':
            slot.is_active = False
        elif action == 'activate':
            slot.is_active = True
        else:
            return Response({'error': 'Invalid action'}, status=400)
        slot.save()
        return Response({'message': f'Slot {slot_id} updated', 'status': slot.status})
    except ParkingSlot.DoesNotExist:
        return Response({'error': 'Slot not found'}, status=404)