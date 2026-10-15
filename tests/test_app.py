"""
Automated tests for the PhishGuard phishing simulator.

Run from the repository root with:
python.exe -m unittest discover -s tests -v

Every test runs against a brand-new temporary SQLite database
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# app.py runs init_db() against a relative 'portal.db' on import
_cwd = os.getcwd()
os.chdir(tempfile.mkdtemp())
import app as portal  # noqa: E402
os.chdir(_cwd)

ADMIN = ("admin", "password")

PROTECTED_PAGES = ["/", "/users", "/users/new", "/departments", "/departments/new",
                   "/scenarios", "/campaigns", "/campaigns/new", "/campaigns/1", "/train"]
ADMIN_PAGES = ["/users", "/users/new", "/users/1/edit", "/departments",
               "/departments/new", "/departments/1/edit", "/scenarios", "/campaigns/new"]


class PortalTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        portal.DB = self.db_path
        portal.init_db()
        portal.app.config["TESTING"] = True
        self.client = portal.app.test_client()

        # Alice is an admin with no login yet; Bob is a learner in campaign 1
        self.run_sql(
            "INSERT INTO user (department_id, email, full_name, role) VALUES "
            "(1, 'alice@company.com', 'Alice Johnson', 'admin'), "
            "(1, 'bob@company.com', 'Bob Smith', 'learner')"
        )
        self.run_sql(
            "INSERT INTO user_campaign (user_id, campaign_id) SELECT id, 1 FROM user "
            "WHERE email = 'bob@company.com'"
        )
        self.run_sql("UPDATE scenario SET correct_answer = 'A'")

    def tearDown(self):
        os.remove(self.db_path)

    # --- helpers ---
    def run_sql(self, sql, args=()):
        conn = portal.get_db()
        rows = conn.execute(sql, args).fetchall()
        conn.commit()
        conn.close()
        return rows

    def login(self, username, password):
        self.client.post("/login", data={"username": username, "password": password})
        with self.client.session_transaction() as s:
            code = s.get("otp_code", "")
        return self.client.post("/otp", data={"otp": code})

    def register(self, username, email, password="pw12345"):
        return self.client.post("/register", data={"username": username, "email": email, "password": password})

    def login_as_bob(self):
        self.register("bob", "bob@company.com")
        self.login("bob", "pw12345")

    def enrolment_id(self, email):
        return self.run_sql(
            "SELECT uc.id FROM user_campaign uc JOIN user u ON u.id = uc.user_id "
            "WHERE u.email = ? AND uc.campaign_id = 1", (email,))[0]["id"]

    def score(self, enrolment_id):
        return self.run_sql("SELECT score FROM user_campaign WHERE id = ?", (enrolment_id,))[0]["score"]

    def scenario_ids(self):
        return [r["id"] for r in self.run_sql(
            "SELECT id FROM campaign_scenario WHERE campaign_id = 1 ORDER BY sequence_order")]

    def answer(self, enrolment_id, scenario_id, choice="A"):
        return self.client.post("/train", data={"action": choice, "user_campaign_id": enrolment_id,
                                                "campaign_scenario_id": scenario_id})

    # --- Expected to pass ---
    def test_TC01_wrong_password_is_rejected(self):
        r = self.client.post("/login", data={"username": ADMIN[0], "password": "wrong"})
        self.assertIn(b"Incorrect username/email or password.", r.data)
        with self.client.session_transaction() as s:
            self.assertNotIn("pending_user", s)

    def test_TC02_password_and_otp_log_in(self):
        r = self.login(*ADMIN)
        self.assertTrue(r.headers["Location"].endswith("/"))
        with self.client.session_transaction() as s:
            self.assertEqual(s["user"], "admin")
            self.assertNotIn("otp_code", s)

    def test_TC03_logout_ends_session(self):
        self.login(*ADMIN)
        self.assertTrue(self.client.get("/logout").headers["Location"].endswith("/login"))
        with self.client.session_transaction() as s:
            self.assertEqual(dict(s), {})
        self.assertTrue(self.client.get("/users").headers["Location"].endswith("/login"))

    def test_TC04_logged_out_visitors_cannot_open_pages(self):
        for path in PROTECTED_PAGES:
            with self.subTest(path=path):
                expected = "/welcome" if path == "/" else "/login"
                self.assertTrue(self.client.get(path).headers["Location"].endswith(expected))

    def test_TC05_learner_blocked_from_admin_pages(self):
        self.login_as_bob()
        for path in ADMIN_PAGES:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)

    def test_TC06_full_training_run_scores_and_completes(self):
        self.login_as_bob()
        bob = self.enrolment_id("bob@company.com")
        for scenario_id in self.scenario_ids():
            self.assertEqual(self.client.get("/train").status_code, 200)
            self.assertEqual(self.answer(bob, scenario_id).status_code, 200)
        row = self.run_sql("SELECT status, score FROM user_campaign WHERE id = ?", (bob,))[0]
        self.assertEqual((row["status"], row["score"]), ("completed", 20))

    def test_TC07_user_input_is_html_escaped(self):
        self.login(*ADMIN)
        self.client.post("/users/new", data={"full_name": "<script>alert(1)</script>", "email": "x@x.com",
                                             "job_title": "", "department_id": "1", "role": "learner"})
        r = self.client.get("/users")
        self.assertNotIn(b"<script>alert(1)</script>", r.data)
        self.assertIn(b"&lt;script&gt;", r.data)

    # --- Known defects: expected to fail until fixed ---
    @unittest.expectedFailure  # DEF-001
    def test_TC08_register_cannot_claim_an_admin_profile(self):
        self.register("mallory", "alice@company.com")
        self.login("mallory", "pw12345")
        self.assertEqual(self.client.get("/users").status_code, 403)

    @unittest.expectedFailure  # DEF-002
    def test_TC09_resubmitting_an_answer_does_not_add_points(self):
        self.login_as_bob()
        bob = self.enrolment_id("bob@company.com")
        for _ in range(5):
            self.answer(bob, self.scenario_ids()[0])
        self.assertEqual(self.score(bob), 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
