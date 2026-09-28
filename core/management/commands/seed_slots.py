from django.core.management.base import BaseCommand

from core.models import ParkingSlot


class Command(BaseCommand):
    help = 'Seed initial parking slots'

    def handle(self, *args, **options):
        slots = [('A-10%d' % i, 'Ground Floor', ParkingSlot.SlotType.COMPACT) for i in range(1, 5)]
        slots.append(('A-105', 'Ground Floor', ParkingSlot.SlotType.SUV))
        slots += [('B-10%d' % i, 'First Floor', ParkingSlot.SlotType.COMPACT) for i in range(1, 5)]
        slots.append(('B-105', 'First Floor', ParkingSlot.SlotType.SUV))

        created = 0
        for slot_id, zone, stype in slots:
            _, was_created = ParkingSlot.objects.get_or_create(
                slot_id=slot_id, defaults={'zone_name': zone, 'slot_type': stype}
            )
            created += was_created

        self.stdout.write(self.style.SUCCESS(f'{created} new slot(s) created, {len(slots)} total checked.'))
