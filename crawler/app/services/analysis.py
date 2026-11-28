"""OpenAI Responses API. 실제 API 호출은 OPENAI_API_KEY가 있을 때만 실행."""

import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app.schemas import ANALYSIS_SCHEMA, AnalysisValidationError, validate_analysis


class AnalysisError(RuntimeError):
    pass


class OpenAIAnalyzer:
    def __init__(self, api_key, model="gpt-4o-mini", timeout=90, transport=urlopen):
        if not api_key:
            raise AnalysisError("OPENAI_API_KEY_MISSING")
        self.api_key, self.model, self.timeout, self.transport = api_key, model, timeout, transport
        self.prompt = (Path(__file__).resolve().parents[1] / "prompts" / "notice_v1.txt").read_text(encoding="utf-8")

    def analyze(self, notice, attachments):
        # 잘린 본문을 전체 분석 결과로 저장하지 않는다.
        text = notice.get("content_text") or ""
        if len(text) > 40000:
            raise AnalysisError("NOTICE_TOO_LONG")
        payload = {
            "model": self.model, "store": False, "instructions": self.prompt,
            "input": json.dumps({"title": notice["title"], "content_text": text,
                                 "attachments": [{"file_name": a["file_name"]} for a in attachments],
                                 "has_images": "<img " in (notice.get("content_html") or "")}, ensure_ascii=False),
            "max_output_tokens": 6000,
            "text": {"format": {"type": "json_schema", "name": "notice_analysis", "strict": True, "schema": ANALYSIS_SCHEMA}},
        }
        request = Request("https://api.openai.com/v1/responses", data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.api_key}, method="POST")
        # 불확실한 POST 결과를 자동 재전송해 중복 과금하지 않는다. 실패 작업은 관리자가 재요청한다.
        try:
            with self.transport(request, timeout=self.timeout) as response:
                body = response.read(2_000_001)
                if len(body) > 2_000_000:
                    raise AnalysisError("AI_RESPONSE_TOO_LARGE")
                data = json.loads(body)
        except HTTPError as exc:
            exc.close()
            raise AnalysisError(f"OPENAI_HTTP_{exc.code}") from None
        except (OSError, ValueError) as exc:
            raise AnalysisError("OPENAI_TRANSPORT_OR_JSON_ERROR") from None
        if data.get("status") != "completed":
            raise AnalysisError("OPENAI_RESPONSE_INCOMPLETE")
        texts = []
        for output in data.get("output", []):
            for content in output.get("content", []):
                if content.get("type") == "refusal":
                    raise AnalysisError("OPENAI_REFUSAL")
                if content.get("type") == "output_text":
                    texts.append(content["text"])
        if len(texts) != 1:
            raise AnalysisError("OPENAI_OUTPUT_MISSING_OR_MULTIPLE")
        try:
            return validate_analysis(json.loads(texts[0]), notice, bool(attachments))
        except (ValueError, TypeError, KeyError) as exc:
            raise AnalysisError("ANALYSIS_VALIDATION_FAILED") from None
