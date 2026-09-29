from django.db import models


class ANPRLog(models.Model):
    class Gate(models.TextChoices):
        ENTRY = 'entry', 'Entry'
        EXIT = 'exit', 'Exit'

    gate = models.CharField(max_length=10, choices=Gate.choices)
    raw_text = models.CharField(max_length=50, blank=True)
    accepted_plate = models.CharField(max_length=15, blank=True)
    confidence = models.FloatField(default=0)
    success = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.gate}: {self.accepted_plate or "no read"} ({self.created_at:%H:%M:%S})'
