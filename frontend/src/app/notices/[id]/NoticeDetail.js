
"use client";

import { useSyncExternalStore } from "react";
import Link from "next/link";
import styles from "./detail.module.css";
import {
  useDemoList,
  initialTasks,
  BOOKMARK_KEY,
  TASK_KEY,
} from "../../demoStorage";

function subscribe(callback) {
  window.addEventListener("storage", callback);
  return () =>
    window.removeEventListener("storage", callback);
}

function getSnapshot() {
  try {
    return localStorage.getItem("gonsadajob_profile");
  } catch {
    return null;
  }
}

function getServerSnapshot() {
  return null;
}

function parseProfile(value) {
  try {
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
}

function normalize(value) {
  return String(value || "").replace(/\s/g, "");
}

function checkCondition(required, actual) {
  if (required === "전체") return true;
  if (!required || !actual) return null;

  return normalize(required) === normalize(actual);
}

function checkEligibility(notice, profile) {
  if (!profile) {
    return {
      status: "추가 확인 필요",
      type: "unknown",
      reason: "개인화 프로필을 먼저 설정해 주세요.",
    };
  }

  const doubleMajorMatch =
    Boolean(profile.doubleMajor) &&
    normalize(notice.department) ===
      normalize(profile.doubleMajor);

  const campus = doubleMajorMatch
    ? true
    : checkCondition(notice.campus, profile.campus);

  const department = doubleMajorMatch
    ? true
    : checkCondition(
        notice.department,
        profile.department
      );

  const grade = checkCondition(
    notice.grade,
    profile.grade
  );

  const residence = checkCondition(
    notice.residence,
    profile.residence
  );

  const conditions = [
    campus, department, grade, residence,
  ];

  if (conditions.includes(false)) {
    return {
      status: "기본 조건 불충족",
      type: "unmatched",
      reason:
        "현재 프로필과 예시 공지의 기본 대상 조건에 차이가 있습니다.",
    };
  }

  if (conditions.includes(null)) {
    return {
      status: "추가 확인 필요",
      type: "unknown",
      reason:
        "입력된 정보만으로는 기본 조건을 모두 확인할 수 없습니다.",
    };
  }

  return {
    status: "기본 조건 충족",
    type: "matched",
    reason:
      "캠퍼스, 학과, 학년 및 거주 방식의 기본 조건이 일치합니다. 세부 신청 자격은 별도 확인이 필요합니다.",
  };
}

export default function NoticeDetail({ notice }) {

  const [bookmarks, setBookmarks] = useDemoList(
    BOOKMARK_KEY,
    []
  );

  const [tasks, setTasks] = useDemoList(
    TASK_KEY,
    initialTasks
  );

  const isBookmarked = bookmarks.includes(notice.id);

  const taskId = `notice-${notice.id}`;

  const savedTask = tasks.find(
    (task) => task.id === taskId
  );

  function toggleBookmark() {
    setBookmarks((previous) =>
      previous.includes(notice.id)
        ? previous.filter((id) => id !== notice.id)
        : [...previous, notice.id]
    );
  }

  function addTask() {
    setTasks((previous) => {
      if (previous.some((task) => task.id === taskId)) {
        return previous;
      }

      return [
        ...previous,
        {
          id: taskId,
          title: notice.title + " 준비",
          date: notice.deadline,
          done: false,
        },
      ];
    });
  }

  function toggleSavedTask() {
    setTasks((previous) =>
      previous.map((task) =>
        task.id === taskId
          ? { ...task, done: !task.done }
          : task
      )
    );
  }

  function removeTask() {
    setTasks((previous) =>
      previous.filter((task) => task.id !== taskId)
    );
  }

  const storedProfile = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot
  );

  const profile = parseProfile(storedProfile);
  const eligibility = checkEligibility(notice, profile);

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Link href="/" className={styles.brand}>
          <span className={styles.logo}>✓</span>
          <div>
            <strong>공사다잡</strong>
            <small>공지사항 다 잡아</small>
          </div>
        </Link>

        <Link href="/" className={styles.backButton}>
          ← 공지 목록
        </Link>
      </header>

      <main className={styles.container}>
        <p className={styles.breadcrumb}>
          대시보드 / 공지사항 / 상세보기
        </p>

        <article className={styles.card}>
          <div className={styles.badges}>
            <span className={styles.category}>
              {notice.category}
            </span>
            <span className={styles.campus}>
              {notice.campus === "전체"
                ? "공통 캠퍼스"
                : notice.campus}
            </span>
            <span className={styles.demo}>
              예시 공지
            </span>
          </div>

          <h1>{notice.title}</h1>

<div className={styles.actionRow}>
  <button
    className={styles.saveButton}
    data-saved={isBookmarked}
    aria-pressed={isBookmarked}
    onClick={toggleBookmark}
  >
    {isBookmarked ? "★ 북마크 저장됨" : "☆ 북마크 추가"}
  </button>
</div>


          <div className={styles.meta}>
            <span>출처: {notice.source}</span>
            <span>게시일: {notice.date}</span>
          </div>

          <div className={styles.deadline}>
            <span>신청 마감일</span>
            <strong>{notice.deadline}</strong>
          </div>

          <section className={styles.summaryBox}>
            <h2>✦ AI 핵심 요약</h2>
            <p>{notice.summary}</p>
            <small>서버 연동 전 테스트용 요약입니다.</small>
          </section>

          <section className={styles.section}>
            <h2>나의 참여 자격 확인</h2>

            <div
              className={styles.eligibility}
              data-type={eligibility.type}
            >
              <strong>{eligibility.status}</strong>
              <p>{eligibility.reason}</p>
            </div>

            <div className={styles.conditions}>
              {[
                ["캠퍼스", notice.campus],
                ["대상 학과", notice.department],
                ["대상 학년", notice.grade],
                ["거주 방식", notice.residence],
              ].map(([label, value]) => (
                <div
                  className={styles.condition}
                  key={label}
                >
                  <span>{label}</span>
                  <strong>{value || "확인 필요"}</strong>
                </div>
              ))}
            </div>

            {!profile && (
              <Link
                href="/onboarding"
                className={styles.profileLink}
              >
                개인화 프로필 설정하기 →
              </Link>
            )}

            <p className={styles.warning}>
              기본 조건 판별은 참고용이며 실제 참여 자격을
              보장하지 않습니다.
            </p>
          </section>

          <section className={styles.section}>
            <h2>공지사항 내용</h2>
            <p>{notice.detail}</p>
          </section>

          <section className={styles.section}>
            <h2>신청 방법 및 준비 사항</h2>
            <p>
              구체적인 신청 절차와 제출 서류는
              공식 공지 원문에서 확인해야 합니다.
            </p>
            
<div className={styles.todo}>
  · 신청 자격 및 일정 확인
</div>

<div className={styles.todo}>
  · 신청 방법 및 제출 서류 확인
</div>

{savedTask ? (
  <div className={styles.savedTask}>
    <label>
      <input
        type="checkbox"
        checked={savedTask.done}
        onChange={toggleSavedTask}
      />
      <span>
        {savedTask.done
          ? "준비 사항 완료"
          : "나의 준비 사항에 추가됨"}
      </span>
    </label>

    <button
      className={styles.removeButton}
      onClick={removeTask}
    >
      삭제
    </button>
  </div>
) : (
  <button
    className={styles.addTaskButton}
    onClick={addTask}
  >
    + 나의 준비 사항에 추가
  </button>
)}

          </section>

          <section className={styles.sourceBox}>
            <h2>공식 공지사항 원문</h2>
            <p>
              실제 원문 링크와 첨부파일은 공지사항
              크롤링 서비스 연동 이후 제공됩니다.
            </p>
          </section>

          <Link href="/" className={styles.mainButton}>
            공지사항 목록으로 돌아가기
          </Link>
        </article>

        <footer className={styles.footer}>
          공사다잡 · 단국대학교 인공지능융합플랫폼 프로젝트
        </footer>
      </main>
    </div>
  );
}
