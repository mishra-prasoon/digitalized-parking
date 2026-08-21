from django.shortcuts import render

def entry_display(request):
    return render(request, 'gate/entry_display.html')

def exit_kiosk(request):
    return render(request, 'gate/exit_kiosk.html')
