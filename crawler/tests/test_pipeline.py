import unittest
from dataclasses import replace

from app.schemas import validate_analysis
from app.services.analysis import AnalysisError
from app.services.notices import NoticeRepository
from app.services.pipeline import Pipeline
from tests.support import FakeAnalyzer, FakeHttp, fixture_analysis, fixture_notice, test_database, test_settings


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.db, self.board_id = test_database()
        self.addCleanup(self.db.close)
        self.repo = NoticeRepository(self.db)
        self.pipeline = Pipeline(self.db, FakeHttp(), FakeAnalyzer(), test_settings())

    def complete(self):
        self.repo.save(self.board_id, fixture_notice())
        return self.pipeline.analyze_one()

    def test_end_to_end_crawl_analysis_and_repeat(self):
        result = self.pipeline.run_once()
        self.assertEqual(result["crawl_jobs"][0]["status"], "SUCCEEDED")
        self.assertEqual(result["analysis_jobs"][0]["status"], "REVIEW_REQUIRED")
        self.assertEqual(self.db.one("SELECT count(*) AS n FROM notices")["n"], 1)
        self.assertEqual(self.pipeline.run_once()["crawl_jobs"], [])
        self.assertEqual(self.repo.save(self.board_id, fixture_notice())[0], "unchanged")
        self.assertEqual(self.db.one("SELECT count(*) AS n FROM notice_analysis")["n"], 1)
        event = self.db.one("SELECT * FROM notice_events")
        self.assertEqual(event["start_at"], "2026-12-10 09:00:00.000000")

    def test_body_change_invalidates_old_analysis_and_dates(self):
        self.complete()
        original = fixture_notice()
        self.repo.save(self.board_id, replace(original, content_text=original.content_text + "\n추가 안내"))
        self.assertEqual(self.db.one("SELECT count(*) AS n FROM notice_analysis WHERE is_current=?", (True,))["n"], 0)
        self.assertIsNone(self.db.one("SELECT start_at FROM notice_events")["start_at"])
        self.assertEqual(self.db.one("SELECT count(*) AS n FROM notice_analysis WHERE status='PENDING'")["n"], 1)

    def test_admin_reanalysis_failure_keeps_previous_current(self):
        self.complete()
        before = self.db.one("SELECT id FROM notice_analysis WHERE is_current=?", (True,))["id"]
        with self.db.transaction():
            self.repo.enqueue_analysis(self.db.one("SELECT * FROM notices"))
        class FailingAnalyzer:
            model = "fixture"
            def analyze(self, *args):
                raise AnalysisError("OPENAI_HTTP_429")
        self.pipeline.analyzer = FailingAnalyzer()
        self.assertEqual(self.pipeline.analyze_one()["status"], "FAILED")
        self.assertEqual(self.db.one("SELECT id FROM notice_analysis WHERE is_current=?", (True,))["id"], before)

    def test_new_result_is_atomically_current_and_reuses_event_id(self):
        self.complete()
        event_id = self.db.one("SELECT id FROM notice_events")["id"]
        with self.db.transaction():
            self.repo.enqueue_analysis(self.db.one("SELECT * FROM notices"))
        self.pipeline.analyze_one()
        self.assertEqual(self.db.one("SELECT count(*) AS n FROM notice_analysis WHERE is_current=?", (True,))["n"], 1)
        self.assertEqual(self.db.one("SELECT id FROM notice_events")["id"], event_id)

    def test_late_analysis_cannot_overwrite_changed_notice(self):
        self.repo.save(self.board_id, fixture_notice())
        job, notice = self.repo.claim_analysis()
        result = validate_analysis(fixture_analysis(), notice)
        self.repo.save(self.board_id, replace(fixture_notice(), title="수정 제목"))
        self.assertFalse(self.repo.complete_analysis(job, result, "fixture"))
        self.assertEqual(self.db.one("SELECT status FROM notice_analysis WHERE id=?", (job["id"],))["status"], "STALE")

    def test_child_write_failure_rolls_back_current_promotion(self):
        self.complete()
        previous = self.db.one("SELECT id FROM notice_analysis WHERE is_current=?", (True,))["id"]
        with self.db.transaction():
            self.repo.enqueue_analysis(self.db.one("SELECT * FROM notices"))
        self.db.execute("CREATE TRIGGER fail_requirement BEFORE INSERT ON notice_requirements BEGIN SELECT RAISE(ABORT, 'test rollback'); END")
        self.assertEqual(self.pipeline.analyze_one()["status"], "FAILED")
        self.assertEqual(self.db.one("SELECT id FROM notice_analysis WHERE is_current=?", (True,))["id"], previous)

    def test_attachment_sync_removes_old_metadata_and_leaves_unread(self):
        self.repo.save(self.board_id, fixture_notice())
        self.assertFalse(self.db.one("SELECT text_extracted FROM notice_attachments")["text_extracted"])
        self.repo.save(self.board_id, replace(fixture_notice(), attachments=[]))
        self.assertEqual(self.db.one("SELECT count(*) AS n FROM notice_attachments")["n"], 0)

    def test_no_key_preserves_analysis_queue(self):
        self.pipeline.analyzer = None
        result = self.pipeline.run_once()
        self.assertIn("analysis_skipped", result)
        self.assertEqual(self.db.one("SELECT status FROM notice_analysis")["status"], "PENDING")

    def test_disabled_source_is_not_scheduled(self):
        self.db.update("source_boards", self.board_id, is_active=False)
        self.assertEqual(self.pipeline.schedule(), 0)

    def test_manual_pending_job_is_consumed_without_rescheduling(self):
        self.pipeline.schedule()
        self.db.execute("UPDATE crawl_logs SET trigger='MANUAL'")
        result = self.pipeline.run_once(scheduled=False)
        self.assertEqual(result["scheduled"], 0)
        self.assertEqual(len(result["crawl_jobs"]), 1)
        self.assertEqual(self.db.one("SELECT trigger FROM crawl_logs")["trigger"], "MANUAL")

    def test_changed_parser_fails_and_does_not_move_checkpoint(self):
        self.pipeline.schedule()
        self.pipeline.http.get = lambda *a: "<html>오류 페이지</html>"
        result = self.pipeline.run_once(scheduled=False)
        self.assertEqual(result["crawl_jobs"][0]["status"], "FAILED")
        self.assertIsNone(self.db.one("SELECT checkpoint FROM source_boards")["checkpoint"])

    def test_recover_marks_interrupted_jobs_failed_without_requeue(self):
        self.pipeline.schedule()
        self.pipeline.claim_crawl()
        self.repo.save(self.board_id, fixture_notice())
        self.repo.claim_analysis()
        result = self.pipeline.recover()
        self.assertEqual(result, {"recovered_crawl_jobs": 1, "recovered_analysis_jobs": 1})
        self.assertIsNone(self.repo.claim_analysis())

    def test_invalid_db_table_is_rejected(self):
        with self.assertRaises(ValueError):
            self.db.insert("user_profiles", user_id="x")

    def test_schema_matches_fixture(self):
        self.db.check_schema()
