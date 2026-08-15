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
        new_status = request.data.get('status')
        if new_status not in ['available', 'occupied', 'booked', 'maintenance']:
            return Response({'error': 'Invalid status'}, status=400)
        slot.status = new_status
        slot.is_occupied = (new_status == 'occupied')
        slot.save()
        return Response({'message': f'Slot {slot_id} updated to {new_status}'})
    except ParkingSlot.DoesNotExist:
        return Response({'error': 'Slot not found'}, status=404)