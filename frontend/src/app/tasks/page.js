
"use client";

import { useState } from "react";
import Link from "next/link";
import {
  useDemoList,
  initialTasks,
  TASK_KEY,
} from "../demoStorage";
import styles from "./tasks.module.css";

export default function TasksPage() {
  const [tasks, setTasks] = useDemoList(
    TASK_KEY,
    initialTasks
  );

  const [filter, setFilter] = useState("all");

  const completedCount = tasks.filter(
    (task) => task.done
  ).length;

  const remainingCount =
    tasks.length - completedCount;

  const progress = tasks.length
    ? Math.round(
        (completedCount / tasks.length) * 100
      )
    : 0;

  function toggleTask(id) {
    setTasks((previous) =>
      previous.map((task) =>
        task.id === id
          ? { ...task, done: !task.done }
          : task
      )
    );
  }

  function removeTask(id) {
    const confirmed = window.confirm(
      "해당 준비 사항을 삭제하시겠습니까?"
    );

    if (!confirmed) return;

    setTasks((previous) =>
      previous.filter((task) => task.id !== id)
    );
  }

  const filteredTasks = tasks
    .filter((task) => {
      if (filter === "pending") return !task.done;
      if (filter === "completed") return task.done;
      return true;
    })
    .sort((a, b) => {
      return String(a.date || "").localeCompare(
        String(b.date || ""),
        undefined,
        { numeric: true }
      );
    });

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Link href="/" className={styles.brand}>
          <div className={styles.logo}>✓</div>

          <div>
            <h1>공사다잡</h1>
            <p>공지사항 다 잡아</p>
          </div>
        </Link>

        <nav className={styles.navigation}>
          <Link href="/dashboard">대시보드</Link>
          <Link href="/notices">전체 공지</Link>
          <Link href="/bookmarks">북마크</Link>
          <Link
            href="/tasks"
            className={styles.active}
            aria-current="page"
          >
            일정 및 To-do
          </Link>
        </nav>
      </header>

      <main className={styles.container}>
        <section className={styles.hero}>
          <p>MY SCHEDULE & TO-DO</p>
          <h2>나의 일정 및 준비 사항</h2>
          <span>
            중요한 공지의 마감일과 준비 사항을
            한곳에서 관리하세요.
          </span>
        </section>

        <div className={styles.stats}>
          <div className={styles.stat}>
            <p>전체 준비 사항</p>
            <strong>{tasks.length}개</strong>
          </div>

          <div className={styles.stat}>
            <p>준비 중</p>
            <strong style={{ color: "#315bea" }}>
              {remainingCount}개
            </strong>
          </div>

          <div className={styles.stat}>
            <p>준비 완료</p>
            <strong style={{ color: "#198754" }}>
              {completedCount}개
            </strong>
          </div>
        </div>

        <section className={styles.progressCard}>
          <div className={styles.progressHeader}>
            <h3>전체 준비 진행률</h3>
            <strong>{progress}%</strong>
          </div>

          <div
            className={styles.progressTrack}
            role="progressbar"
            aria-label="준비 진행률"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className={styles.progressBar}
              style={{ width: `${progress}%` }}
            />
          </div>
        </section>

        <section className={styles.listCard}>
          <div className={styles.listHeader}>
            <div>
              <h3>준비 사항 목록</h3>
              <p>마감일이 빠른 순서대로 표시됩니다.</p>
            </div>

            <div className={styles.filters}>
              {[
                ["all", "전체"],
                ["pending", "준비 중"],
                ["completed", "완료"],
              ].map(([value, label]) => (
                <button
                  key={value}
                  className={
                    filter === value
                      ? styles.selected
                      : ""
                  }
                  aria-pressed={filter === value}
                  onClick={() => setFilter(value)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {filteredTasks.length === 0 && (
            <div className={styles.empty}>
              <p>표시할 준비 사항이 없습니다.</p>
              <Link href="/notices">
                공지사항 확인하기 →
              </Link>
            </div>
          )}

          {filteredTasks.map((task) => {
            const noticeId = String(task.id).match(
              /^notice-(\d+)$/
            )?.[1];

            return (
              <article
                key={task.id}
                className={styles.task}
                data-done={task.done}
              >
                <label className={styles.taskCheck}>
                  <input
                    type="checkbox"
                    checked={task.done}
                    onChange={() => toggleTask(task.id)}
                  />

                  <div>
                    <strong
                      className={
                        task.done
                          ? styles.completed
                          : ""
                      }
                    >
                      {task.title}
                    </strong>

                    <p>
                      마감일 {task.date || "미정"}
                    </p>
                  </div>
                </label>

                <div className={styles.taskActions}>
                  {noticeId && (
                    <Link href={`/notices/${noticeId}`}>
                      관련 공지 →
                    </Link>
                  )}

                  <button
                    onClick={() => removeTask(task.id)}
                  >
                    삭제
                  </button>
                </div>
              </article>
            );
          })}
        </section>

        <div className={styles.info}>
          현재 준비 사항은 브라우저에 저장되는
          테스트용 데이터입니다. 실제 사용자별 일정 관리는
          서버 연동 이후 제공됩니다.
        </div>

        <Link
          href="/dashboard"
          className={styles.back}
        >
          ← 대시보드로 돌아가기
        </Link>

        <footer className={styles.footer}>
          공사다잡 · 단국대학교 인공지능융합플랫폼 프로젝트
        </footer>
      </main>
    </div>
  );
}
