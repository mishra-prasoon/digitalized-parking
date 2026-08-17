from django.shortcuts import render

def home(request):
    return render(request, 'parking/home.html')

def slots_view(request):
    return render(request, 'parking/slots.html')

def book_view(request):
    return render(request, 'parking/book.html')

def dashboard_view(request):
    return render(request, 'parking/dashboard.html')

def anpr_demo(request):
    return render(request, 'parking/anpr_demo.html')

def payment_view(request):
    return render(request, 'parking/payment.html')