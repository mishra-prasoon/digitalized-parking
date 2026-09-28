from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

CustomUser = get_user_model()


class RegistrationTests(TestCase):
    def test_registration_creates_normal_user_role(self):
        response = self.client.post(reverse('register'), {
            'username': 'alice',
            'email': 'alice@example.com',
            'phone_number': '9999999999',
            'password1': 'a-strong-pass-1',
            'password2': 'a-strong-pass-1',
        })
        user = CustomUser.objects.get(username='alice')
        self.assertEqual(user.role, CustomUser.Role.USER)
        self.assertRedirects(response, '/portal/')

    def test_forged_role_field_is_ignored(self):
        self.client.post(reverse('register'), {
            'username': 'bob',
            'email': 'bob@example.com',
            'phone_number': '',
            'password1': 'a-strong-pass-1',
            'password2': 'a-strong-pass-1',
            'role': 'staff',   # attempted forgery — form has no such field
        })
        user = CustomUser.objects.get(username='bob')
        self.assertEqual(user.role, CustomUser.Role.USER)

    def test_duplicate_username_rejected(self):
        CustomUser.objects.create_user(username='carol', password='a-strong-pass-1')
        response = self.client.post(reverse('register'), {
            'username': 'carol',
            'email': 'carol2@example.com',
            'phone_number': '',
            'password1': 'a-strong-pass-1',
            'password2': 'a-strong-pass-1',
        })
        self.assertEqual(CustomUser.objects.filter(username='carol').count(), 1)
        self.assertContains(response, 'already exists')


class RoleRedirectTests(TestCase):
    def test_normal_user_redirects_to_portal(self):
        CustomUser.objects.create_user(username='dave', password='a-strong-pass-1', role=CustomUser.Role.USER)
        self.client.login(username='dave', password='a-strong-pass-1')
        response = self.client.get(reverse('dashboard_redirect'))
        self.assertRedirects(response, reverse('user_portal'))

    def test_staff_redirects_to_dashboard(self):
        CustomUser.objects.create_user(username='eve', password='a-strong-pass-1', role=CustomUser.Role.STAFF)
        self.client.login(username='eve', password='a-strong-pass-1')
        response = self.client.get(reverse('dashboard_redirect'))
        self.assertRedirects(response, reverse('staff_dashboard'))


class AccessControlTests(TestCase):
    def test_staff_dashboard_rejects_normal_user(self):
        CustomUser.objects.create_user(username='frank', password='a-strong-pass-1', role=CustomUser.Role.USER)
        self.client.login(username='frank', password='a-strong-pass-1')
        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_staff_dashboard_rejects_anonymous(self):
        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 302)   # redirected to login by the middleware

    def test_portal_rejects_anonymous(self):
        response = self.client.get(reverse('user_portal'))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_access_dashboard(self):
        CustomUser.objects.create_user(username='grace', password='a-strong-pass-1', role=CustomUser.Role.STAFF)
        self.client.login(username='grace', password='a-strong-pass-1')
        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 200)