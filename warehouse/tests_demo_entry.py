"""Link /demo/ (wejście bez logowania); reset danych demo — `tests_demo_limits.py`."""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings

from .models import LoginEvent, Role
from .tests_recruiter import _demo_user


@override_settings(DEMO_MODE=True)
class DemoStartTests(TestCase):
    def test_logs_in_and_starts_tour(self):
        user = _demo_user()
        resp = self.client.get("/demo/")
        self.assertRedirects(resp, "/?demo=1")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_does_not_switch_logged_in_user(self):
        _demo_user()
        admin = User.objects.create_superuser("admin", password="x")
        self.client.force_login(admin)
        self.client.get("/demo/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), admin.pk)

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post("/demo/").status_code, 405)

    def test_missing_account_goes_to_login(self):
        resp = self.client.get("/demo/", follow=True)
        self.assertContains(resp, "Konto demo nie jest jeszcze utworzone")
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(DEMO_USER="admin")
    def test_only_demo_accounts(self):
        User.objects.create_superuser("admin", password="x")
        self.client.get("/demo/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_page_links_to_tour(self):
        self.assertContains(self.client.get("/login/"), 'href="/demo/"')


class DemoEntryOffTests(TestCase):
    def test_endpoints_404_without_demo_mode(self):
        _demo_user(role=Role.OPERATOR)
        self.assertEqual(self.client.get("/demo/").status_code, 404)


@override_settings(DEMO_MODE=True)
class DemoEntryRateLimitTests(TestCase):
    """US-005 / SEC-040: limit anonimowych wejść do demo na IP."""

    def setUp(self):
        from .demo import DEMO_ENTRY_RATE_LIMIT

        cache.clear()
        self.limit = DEMO_ENTRY_RATE_LIMIT
        _demo_user()

    def test_demo_start_limited_without_new_session(self):
        for _ in range(self.limit):
            self.client.logout()
            self.assertEqual(self.client.get("/demo/").status_code, 302)
        self.client.logout()
        events = LoginEvent.objects.count()
        resp = self.client.get("/demo/")
        self.assertEqual(resp.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(LoginEvent.objects.count(), events)

    def test_demo_login_post_limited(self):
        for _ in range(self.limit):
            self.client.post("/login/demo/")
        self.client.logout()
        events = LoginEvent.objects.count()
        self.assertEqual(self.client.post("/login/demo/").status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(LoginEvent.objects.count(), events)

    def test_limit_is_per_ip(self):
        for _ in range(self.limit + 1):
            self.client.get("/demo/", REMOTE_ADDR="198.51.100.1")
        self.client.logout()
        resp = self.client.get("/demo/", REMOTE_ADDR="198.51.100.2")
        self.assertEqual(resp.status_code, 302)

    def test_successful_entry_logs_no_ip(self):
        self.client.get("/demo/", REMOTE_ADDR="198.51.100.9")
        event = LoginEvent.objects.get(kind=LoginEvent.Kind.LOGIN)
        self.assertIsNone(event.ip)
        self.assertEqual(event.user_agent, "")

    def test_logged_in_refresh_not_counted(self):
        """Uwaga [SEC] US-005: zalogowany nie zużywa limitu anonimowych wejść."""
        self.client.get("/demo/")
        for _ in range(self.limit + 5):
            self.assertEqual(self.client.get("/demo/").status_code, 302)
        self.client.logout()
        self.assertEqual(self.client.get("/demo/").status_code, 302)
