"""Export the evaluation SQLite DB into `quiz/quiz_data.js` for the static quiz page."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def strip_personal(exams: list[dict]) -> None:
    # 공개 배포본에는 본인의 응시 점수와 선택한 답을 남기지 않는다.
    for e in exams:
        e["score"] = None
        for q in e["questions"]:
            q["userOption"] = None


def load_exams(db_path: Path) -> list[dict]:
    # 원본 DB를 실수로 수정하지 않도록 읽기 전용 URI로 연다.
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        exams = []
        for e in conn.execute(
            "SELECT * FROM exams ORDER BY CASE track WHEN 'CV' THEN 0 ELSE 1 END, day"
        ):
            questions = []
            for q in conn.execute(
                "SELECT * FROM questions WHERE exam_id = ? ORDER BY question_no", (e["exam_id"],)
            ):
                options = [
                    {"no": o["option_no"], "text": o["content"]}
                    for o in conn.execute(
                        "SELECT option_no, content FROM options WHERE question_id = ? ORDER BY option_no",
                        (q["question_id"],),
                    )
                ]
                questions.append(
                    {
                        "id": q["question_id"],
                        "no": q["question_no"],
                        "title": q["title"],
                        "description": q["description"] or "",
                        "points": q["points"],
                        "correct": q["correct_option"],
                        "userOption": q["user_option"],
                        "explanation": q["explanation"] or "",
                        "options": options,
                    }
                )
            exams.append(
                {
                    "id": e["exam_id"],
                    "title": e["title"],
                    "track": e["track"],
                    "day": e["day"],
                    "passingScore": e["passing_score"],
                    "score": e["score"],
                    "questions": questions,
                }
            )
        return exams
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "docs" / "multicampus_eval_CV1-NLP6.db")
    parser.add_argument("--out", type=Path, default=ROOT / "quiz" / "quiz_data.js")
    parser.add_argument("--public", action="store_true", help="Strip personal score and chosen answers")
    args = parser.parse_args()

    exams = load_exams(args.db)
    if args.public:
        strip_personal(exams)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # fetch() 대신 <script>로 싣는 이유: file:// 로 열 때 브라우저가 로컬 JSON fetch를 막기 때문이다.
    payload = json.dumps(exams, ensure_ascii=False, indent=1)
    args.out.write_text(f"window.QUIZ_DATA = {payload};\n", encoding="utf-8")
    n_q = sum(len(e["questions"]) for e in exams)
    print(f"wrote {args.out} ({len(exams)} exams, {n_q} questions)")


if __name__ == "__main__":
    main()
