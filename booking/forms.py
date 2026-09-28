from django import forms

from .models import Booking


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['vehicle', 'slot', 'start_time', 'end_time']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields['vehicle'].queryset = self.fields['vehicle'].queryset.filter(owner=user)

    def save(self, commit=True):
        booking = super().save(commit=False)
        booking.user = self.user
        booking.full_clean()
        if commit:
            booking.save()
        return booking
