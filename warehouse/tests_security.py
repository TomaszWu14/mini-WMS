"""Testy regresji dla ryzyk bezpieczeństwa z docs/AUDYT.md (R1…) — historyjki US-001…"""

from django.contrib.auth.models import User
from django.test import TestCase

from .models import Profile, Role


class SuperuserProtectionTests(TestCase):
    """US-001 / R1: rola Administrator nie edytuje konta superusera."""

    def setUp(self):
        self.root = User.objects.create_superuser("root", "", "RootPass123!")
        self.admin = User.objects.create_user("adm", password="AdmPass123!")
        Profile.objects.filter(user=self.admin).update(role=Role.ADMIN)
        self.operator = User.objects.create_user("op1", password="OpPass123!")
        self.url = f"/uzytkownicy/{self.root.pk}/"

    def _login_admin(self):
        self.assertTrue(self.client.login(username="adm", password="AdmPass123!"))

    def test_admin_cannot_change_superuser_password(self):
        self._login_admin()
        resp = self.client.post(
            self.url,
            {"role": Role.ADMIN, "is_active": "on", "new_password": "Przejete123!"},
        )
        self.assertEqual(resp.status_code, 403)
        self.root.refresh_from_db()
        self.assertTrue(self.root.check_password("RootPass123!"))

    def test_admin_cannot_deactivate_superuser(self):
        self._login_admin()
        resp = self.client.post(self.url, {"role": Role.ADMIN, "new_password": ""})
        self.assertEqual(resp.status_code, 403)
        self.root.refresh_from_db()
        self.assertTrue(self.root.is_active)

    def test_admin_cannot_change_superuser_role(self):
        self._login_admin()
        resp = self.client.post(self.url, {"role": Role.VIEWER, "is_active": "on"})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Profile.objects.get(user=self.root).role, Role.ADMIN)

    def test_admin_cannot_open_superuser_edit(self):
        self._login_admin()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "Brak uprawnień", status_code=403)

    def test_user_list_hides_edit_link_for_superuser(self):
        self._login_admin()
        resp = self.client.get("/uzytkownicy/")
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, f'href="{self.url}"')
        self.assertContains(resp, f'href="/uzytkownicy/{self.operator.pk}/"')

    def test_superuser_can_edit_superuser(self):
        other = User.objects.create_superuser("root2", "", "Root2Pass123!")
        self.assertTrue(self.client.login(username="root", password="RootPass123!"))
        resp = self.client.post(
            f"/uzytkownicy/{other.pk}/",
            {"role": Role.ADMIN, "is_active": "on", "new_password": "NoweHaslo456!"},
        )
        self.assertEqual(resp.status_code, 302)
        other.refresh_from_db()
        self.assertTrue(other.check_password("NoweHaslo456!"))

    def test_admin_can_still_edit_operator(self):
        self._login_admin()
        resp = self.client.post(
            f"/uzytkownicy/{self.operator.pk}/",
            {"role": Role.VIEWER, "is_active": "on", "new_password": ""},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Profile.objects.get(user=self.operator).role, Role.VIEWER)

    def test_admin_cannot_edit_staff_account(self):
        staff = User.objects.create_user(
            "panel", password="StaffPass123!", is_staff=True
        )
        self._login_admin()
        resp = self.client.post(
            f"/uzytkownicy/{staff.pk}/",
            {"role": Role.ADMIN, "is_active": "on", "new_password": "Przejete123!"},
        )
        self.assertEqual(resp.status_code, 403)
        staff.refresh_from_db()
        self.assertTrue(staff.check_password("StaffPass123!"))

    def test_admin_cannot_grant_superuser_via_extra_fields(self):
        self._login_admin()
        resp = self.client.post(
            f"/uzytkownicy/{self.operator.pk}/",
            {
                "role": Role.ADMIN,
                "is_active": "on",
                "is_superuser": "on",
                "is_staff": "on",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.operator.refresh_from_db()
        self.assertFalse(self.operator.is_superuser)
        self.assertFalse(self.operator.is_staff)
