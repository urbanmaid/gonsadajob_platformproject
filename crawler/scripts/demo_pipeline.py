"""네트워크·API 키 없이 메모리 DB에서 수집→분석→중복 방지 흐름을 재현한다."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.pipeline import Pipeline
from tests.support import FakeAnalyzer, FakeHttp, fixture_notice, test_database, test_settings


def main():
    db, board_id = test_database()
    try:
        pipeline = Pipeline(db, FakeHttp(), FakeAnalyzer(), test_settings())
        result = pipeline.run_once()
        repeated, _ = pipeline.notices.save(board_id, fixture_notice())
        print(json.dumps({"mode": "OFFLINE_FIXTURE", "real_api_called": False,
                          "pipeline": result, "repeat_save": repeated,
                          "notice_count": db.one("SELECT count(*) AS n FROM notices")["n"],
                          "current_analysis_count": db.one("SELECT count(*) AS n FROM notice_analysis WHERE is_current=?", (True,))["n"]},
                         ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
