"""서버 코드를 실행하지 않고 8개 테이블의 컬럼 이름을 AST로 비교한다."""

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import TABLES


def check_contract(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    actual = {}
    for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
        table = next((n.value.value for n in cls.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in n.targets)), None)
        if table not in TABLES:
            continue
        columns = set()
        for node in cls.body:
            if not isinstance(node, ast.AnnAssign):
                continue
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "relationship":
                continue
            columns.add(node.target.id)
        if any(isinstance(base, ast.Name) and base.id == "TimestampMixin" for base in cls.bases):
            columns.update({"created_at", "updated_at"})
        actual[table] = columns
    errors = []
    for table, columns in TABLES.items():
        expected = set(columns.split())
        if actual.get(table) != expected:
            errors.append(f"{table}: expected={sorted(expected)}, actual={sorted(actual.get(table, set()))}")
    return errors


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "../server/app/models.py"
    errors = check_contract(path)
    print("\n".join(errors) if errors else "OK: 기반 서버 공통 8개 테이블의 컬럼 이름 일치")
    sys.exit(bool(errors))
