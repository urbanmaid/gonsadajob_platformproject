import copy
import io
import json
import unittest

from app.schemas import AnalysisValidationError, validate_analysis
from app.services.analysis import AnalysisError, OpenAIAnalyzer
from tests.support import fixture_analysis, fixture_notice


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        notice = fixture_notice()
        self.notice = {"title": notice.title, "content_text": notice.content_text, "content_html": ""}
        self.raw = fixture_analysis()

    def test_valid_structured_analysis(self):
        result = validate_analysis(self.raw, self.notice)
        self.assertFalse(result["review_required"])
        self.assertEqual(len(result["requirements"]), 2)

    def test_unread_attachment_guards_every_or_group(self):
        second = copy.deepcopy(self.raw["requirements"][0])
        second["logic_group"] = 2
        self.raw["requirements"].append(second)
        result = validate_analysis(self.raw, self.notice, True)
        self.assertTrue(result["review_required"])
        self.assertEqual({r["logic_group"] for r in result["requirements"] if r["type"] == "other"}, {1, 2})

    def test_optional_only_group_cannot_be_eligible(self):
        for req in self.raw["requirements"]:
            req["mandatory"] = False
        result = validate_analysis(self.raw, self.notice)
        self.assertTrue(any(r["type"] == "other" and r["mandatory"] for r in result["requirements"]))

    def test_unknown_audience_is_not_no_requirements(self):
        self.raw.update(target_scope="unknown", target_evidence="", requirements=[])
        result = validate_analysis(self.raw, self.notice)
        self.assertEqual(result["requirements"][0]["type"], "other")

    def test_empty_body_and_image_require_review(self):
        self.raw.update(target_scope="unknown", target_evidence="", requirements=[], events=[])
        result = validate_analysis(self.raw, {"title": "그림", "content_text": "", "content_html": '<img src="x">'})
        self.assertTrue(result["review_required"])

    def test_hallucinated_condition_evidence_is_rejected(self):
        self.raw["requirements"][0]["evidence_text"] = "TOEIC 900점 이상"
        with self.assertRaises(AnalysisValidationError):
            validate_analysis(self.raw, self.notice)

    def test_unknown_fields_and_nan_confidence_are_rejected(self):
        invalid = copy.deepcopy(self.raw)
        invalid["invented"] = "x"
        with self.assertRaises(AnalysisValidationError):
            validate_analysis(invalid, self.notice)
        self.raw["requirements"][0]["confidence"] = float("nan")
        with self.assertRaises(AnalysisValidationError):
            validate_analysis(self.raw, self.notice)

    def test_numeric_year_and_language_unit_validation(self):
        self.raw["requirements"][1]["value"] = "3학년"
        with self.assertRaises(AnalysisValidationError):
            validate_analysis(self.raw, self.notice)
        self.raw["requirements"][1].update(type="language_score", value="800", unit=None)
        with self.assertRaises(AnalysisValidationError):
            validate_analysis(self.raw, self.notice)

    def test_date_only_deadline_ends_in_korean_time(self):
        self.raw["events"][0]["precision"] = "date"
        self.raw["events"][0]["evidence_text"] = "신청 마감: 2026.12.10."
        result = validate_analysis(self.raw, self.notice)
        self.assertEqual(result["events"][0]["start_at"], "2026-12-10T23:59:59+09:00")

    def test_unsupported_date_is_cleared(self):
        self.raw["events"][0]["start_at"] = "2027-12-10T18:00:00+09:00"
        result = validate_analysis(self.raw, self.notice)
        self.assertIsNone(result["events"][0]["start_at"])
        self.assertEqual(result["events"][0]["precision"], "unknown")

    def test_naive_datetime_is_rejected(self):
        self.raw["events"][0]["start_at"] = "2026-12-10T18:00:00"
        with self.assertRaises(AnalysisValidationError):
            validate_analysis(self.raw, self.notice)

    def test_invented_time_is_marked_unknown(self):
        self.raw["events"][0]["start_at"] = "2026-12-10T17:30:00+09:00"
        result = validate_analysis(self.raw, self.notice)
        self.assertEqual(result["events"][0]["precision"], "unknown")
        self.assertIsNone(result["events"][0]["start_at"])
        self.assertTrue(result["review_required"])

    def test_openai_request_and_response_contract_without_network(self):
        requests = []
        def transport(request, timeout):
            requests.append(json.loads(request.data))
            return io.BytesIO(json.dumps({"status": "completed", "output": [{"type": "message", "content": [
                {"type": "output_text", "text": json.dumps(self.raw)}]}]}).encode())
        analyzer = OpenAIAnalyzer("test-placeholder", transport=transport)
        result = analyzer.analyze(self.notice, [])
        self.assertFalse(requests[0]["store"])
        self.assertTrue(requests[0]["text"]["format"]["strict"])
        self.assertEqual(result["category"], "비교과")

    def test_refusal_and_incomplete_do_not_become_success(self):
        for data in ({"status": "incomplete"}, {"status": "completed", "output": [{"content": [{"type": "refusal"}]}]}):
            with self.subTest(data=data):
                analyzer = OpenAIAnalyzer("test-placeholder", transport=lambda *a, **k: io.BytesIO(json.dumps(data).encode()))
                with self.assertRaises(AnalysisError):
                    analyzer.analyze(self.notice, [])
