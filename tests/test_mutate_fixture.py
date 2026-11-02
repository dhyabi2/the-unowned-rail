import hashlib, os, sys, tempfile, unittest, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import mutate_fixture as mf


class T(unittest.TestCase):
    def test_each_step_changes_body_and_log_matches(self):
        d = tempfile.mkdtemp(); mf.D = d; mf.BODY = os.path.join(d, "b"); mf.LOG = os.path.join(d, "l")
        t = datetime.datetime(2026, 11, 2, 18, 0, 0, tzinfo=datetime.timezone.utc)
        a = mf.step(t); ha = hashlib.sha256(open(mf.BODY, "rb").read()).hexdigest()
        b = mf.step(t + datetime.timedelta(minutes=10)); hb = hashlib.sha256(open(mf.BODY, "rb").read()).hexdigest()
        self.assertNotEqual(ha, hb)
        self.assertEqual((a["sha256"], b["sha256"]), (ha, hb))
        self.assertEqual(len(mf.log_rows()), 2)

if __name__ == "__main__": unittest.main()
