
"use client";

import { useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import styles from "./page.module.css";
import {
  useDemoList,
  initialTasks,
  BOOKMARK_KEY,
  TASK_KEY,
} from "./demoStorage";

// 서버 연동 전 테스트용 공지사항
import { notices } from "./noticeData";


const categories = [
  "학사", "장학", "행사", "기숙사",
  "취업", "봉사", "학생복지", "공모전",
];

// 브라우저에 저장된 개인화 프로필 읽기
function subscribeProfile(callback) {
  window.addEventListener("storage", callback);
  return () => window.removeEventListener("storage", callback);
}

function getProfileSnapshot() {
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
    const data = value ? JSON.parse(value) : null;
    return data && typeof data === "object" ? data : null;
  } catch {
    return null;
  }
}

function normalize(value) {
  return String(value || "").replace(/\s/g, "").toLowerCase();
}

export default function Dashboard({
  initialMenu = "dashboard",
}) {
  const storedProfile = useSyncExternalStore(
    subscribeProfile,
    getProfileSnapshot,
    getServerSnapshot
  );

  const userProfile = parseProfile(storedProfile);

  const [tasks, setTasks] = useDemoList(
  TASK_KEY,
  initialTasks
);
  const [bookmarks, setBookmarks] = useDemoList(
  BOOKMARK_KEY,
  []
);
  const [search, setSearch] = useState("");
  const [campus, setCampus] = useState(null);
  const [department, setDepartment] = useState(null);
  const [grade, setGrade] = useState(null);
  const [category, setCategory] = useState(null);
  const [residence, setResidence] = useState(null);
  const activeMenu = initialMenu;
const router = useRouter();
  const interests = Array.isArray(userProfile?.interests)
    ? userProfile.interests
    : [];

  const selectedCampus =
    campus ?? userProfile?.campus ?? "전체";

  const selectedDepartment =
    department ?? (userProfile ? "내 전공" : "전체");

  const selectedGrade =
    grade ?? userProfile?.grade ?? "전체";

  const selectedCategory =
    category ?? (interests.length ? "내 관심 분야" : "전체");

  const selectedResidence =
    residence ?? userProfile?.residence ?? "전체";

  const departmentOptions = [
    ...new Set([
      "소프트웨어학과",
      "식량생명공학과",
      "경영학과",
      userProfile?.department,
      userProfile?.doubleMajor,
    ].filter(Boolean)),
  ];

  const completedCount = tasks.filter((task) => task.done).length;
  const progress = tasks.length
  ? Math.round((completedCount / tasks.length) * 100)
  : 0;

  const filtersDisabled = activeMenu !== "dashboard";

  function toggleTask(id) {
    setTasks((previous) =>
      previous.map((task) =>
        task.id === id ? { ...task, done: !task.done } : task
      )
    );
  }

  function toggleBookmark(id) {
    setBookmarks((previous) =>
      previous.includes(id)
        ? previous.filter((item) => item !== id)
        : [...previous, id]
    );
  }

  function resetFilters() {
    setSearch("");
    setCampus("전체");
    setDepartment("전체");
    setGrade("전체");
    setCategory("전체");
    setResidence("전체");
  }

  function applyProfile() {
    setSearch("");
    setCampus(null);
    setDepartment(null);
    setGrade(null);
    setCategory(null);
    setResidence(null);
    if (activeMenu !== "dashboard") {
  router.push("/dashboard");
}
  }

  const filteredNotices = notices.filter((notice) => {
    const keyword = search.trim().toLowerCase();

    const matchesSearch = [
      notice.title,
      notice.summary,
      notice.source,
      notice.category,
    ].some((text) => text.toLowerCase().includes(keyword));

    if (!matchesSearch) return false;

    if (activeMenu === "all") return true;

    if (activeMenu === "bookmarks") {
      return bookmarks.includes(notice.id);
    }

    const matchesDoubleMajor =
      Boolean(userProfile?.doubleMajor) &&
      normalize(notice.department) ===
        normalize(userProfile.doubleMajor);

    const matchesCampus =
      selectedCampus === "전체" ||
      notice.campus === "전체" ||
      notice.campus === selectedCampus ||
      (campus === null &&
        selectedDepartment === "내 전공" &&
        matchesDoubleMajor);

    const matchesDepartment =
      selectedDepartment === "전체" ||
      notice.department === "전체" ||
      (selectedDepartment === "내 전공"
        ? normalize(notice.department) ===
            normalize(userProfile?.department) ||
          matchesDoubleMajor
        : normalize(notice.department) ===
          normalize(selectedDepartment));

    const matchesGrade =
      selectedGrade === "전체" ||
      notice.grade === "전체" ||
      notice.grade === selectedGrade;

    const matchesCategory =
      selectedCategory === "전체" ||
      (selectedCategory === "내 관심 분야"
        ? interests.includes(notice.category) || notice.common === true
        : notice.category === selectedCategory);

    const matchesResidence =
      selectedResidence === "전체" ||
      notice.residence === "전체" ||
      notice.residence === selectedResidence;

    return (
      matchesCampus &&
      matchesDepartment &&
      matchesGrade &&
      matchesCategory &&
      matchesResidence
    );
  });

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.brand}>
          <div className={styles.logo}>✓</div>
          <div>
            <h1>공사다잡</h1>
            <p>공지사항 다 잡아</p>
          </div>
        </div>

        
<nav className={styles.navigation}>
  <Link
    href="/dashboard"
    className={
      activeMenu === "dashboard"
        ? styles.active
        : ""
    }
  >
    대시보드
  </Link>

  <Link
    href="/notices"
    className={
      activeMenu === "all"
        ? styles.active
        : ""
    }
  >
    전체 공지
  </Link>

  <Link
    href="/bookmarks"
    className={
      activeMenu === "bookmarks"
        ? styles.active
        : ""
    }
  >
    북마크 ({bookmarks.length})
  </Link>

  <Link href="/tasks">
    일정 및 To-do
  </Link>
</nav>


        <span className={styles.demo}>프로토타입</span>
      </header>

      <main className={styles.dashboard}>
        <aside className={styles.sidebar}>
          <section className={styles.taskSection}>
            <p className={styles.eyebrow}>MY CHECKLIST</p>
            <h2>나의 준비 사항</h2>
            <p className={styles.description}>
              중요한 일정과 준비물을 놓치지 마세요.
            </p>

            <div className={styles.progressInfo}>
              <span>준비 진행률</span>
              <strong>{progress}%</strong>
            </div>

            <div className={styles.progressTrack}>
              <div
                className={styles.progressBar}
                style={{ width: `${progress}%` }}
              />
            </div>

            <p className={styles.taskCount}>
              {tasks.length}개 중 {completedCount}개 완료
            </p>

            <div className={styles.taskList}>
              {tasks.map((task) => (
                <label className={styles.task} key={task.id}>
                  <input
                    type="checkbox"
                    checked={task.done}
                    onChange={() => toggleTask(task.id)}
                  />
                  <div>
                    <span className={task.done ? styles.completed : ""}>
                      {task.title}
                    </span>
                    <small>마감 {task.date}</small>
                  </div>
                </label>
              ))}
            </div>
          </section>

          <div className={styles.account}>
            <div className={styles.avatar}>
              {userProfile ? "D" : "U"}
            </div>
            <div>
              <strong>
                {userProfile ? "개인화 프로필" : "게스트 사용자"}
              </strong>

              {userProfile && (
                <>
                  <p>단국대학교 {userProfile.campus}</p>
                  <p>{userProfile.department}</p>
                  {userProfile.doubleMajor && (
                    <p>복수전공: {userProfile.doubleMajor}</p>
                  )}
                  <p>
                    {userProfile.grade} · {userProfile.residence}
                  </p>
                </>
              )}

              <p>
                <Link href="/login">로그인</Link>
                {" · "}
                <Link href="/register">회원가입</Link>
              </p>
              <p>
                <Link href={userProfile ? "/settings" : "/onboarding"}>
  {userProfile ? "마이페이지 →" : "개인화 프로필 설정 →"}
</Link>
              </p>
            </div>
          </div>
        </aside>

        <section className={styles.content}>
          <div className={styles.welcome}>
            <p className={styles.eyebrow}>
              DANKOOK UNIVERSITY · CAMPUS NOTICE
            </p>
            <h2>학교 소식, 이제 한곳에서.</h2>
            <p>나에게 필요한 단국대학교 공지사항을 확인하세요.</p>
          </div>

          {userProfile ? (
            <div className={styles.profileBanner}>
              <div>
                <strong>나의 개인화 프로필</strong>
                <p>
                  {userProfile.campus} · {userProfile.department}
                  {userProfile.doubleMajor
                    ? ` / ${userProfile.doubleMajor}`
                    : ""}
                  {" · "}{userProfile.grade}
                </p>
                <p>
                  관심 분야: {interests.length
                    ? interests.join(", ")
                    : "전체"}
                </p>
              </div>
              <Link href="/settings">프로필 수정 →</Link>
            </div>
          ) : (
            <div className={styles.profileBanner}>
              <div>
                <strong>나만의 맞춤 공지사항을 만나보세요.</strong>
                <p>학과와 관심 분야를 설정하면 맞춤 공지를 제공합니다.</p>
              </div>
              <Link href="/onboarding">프로필 설정 →</Link>
            </div>
          )}

          <div className={styles.noticeHeader}>
            <div>
              <h2>
                {activeMenu === "bookmarks"
                  ? "저장한 공지사항"
                  : activeMenu === "all"
                  ? "전체 공지사항"
                  : "맞춤 공지사항"}
              </h2>
              <p>총 {filteredNotices.length}개의 공지사항 · 예시 데이터</p>
            </div>

            <input
              className={styles.search}
              type="search"
              placeholder="공지사항 검색"
              aria-label="공지사항 검색"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>

          <div className={styles.noticeGrid}>
            {filteredNotices.map((notice) => (
              <article className={styles.noticeCard} key={notice.id}>
                <div className={styles.cardTop}>
                  <span
                    className={styles.category}
                    data-category={notice.category}
                  >
                    {notice.category}
                  </span>
                  <button
                    className={styles.bookmark}
                    aria-label={
                      bookmarks.includes(notice.id)
                        ? "북마크 해제"
                        : "북마크 추가"
                    }
                    aria-pressed={bookmarks.includes(notice.id)}
                    onClick={() => toggleBookmark(notice.id)}
                  >
                    {bookmarks.includes(notice.id) ? "★" : "☆"}
                  </button>
                </div>

                <h3>{notice.title}</h3>

                <p className={styles.campusLabel}>
                  {notice.campus === "전체"
                    ? "공통 캠퍼스"
                    : notice.campus}
                </p>

                <span className={styles.aiLabel}>AI 요약 예시</span>
                <p className={styles.summary}>{notice.summary}</p>

                <div className={styles.cardMeta}>
                  <span>{notice.source}</span>
                  <span>{notice.date}</span>
                </div>

                <div className={styles.cardBottom}>
                  <strong>마감 {notice.deadline}</strong>
                                    <Link href={`/notices/${notice.id}`}>
                    자세히 보기 →
                  </Link>
                </div>

              </article>
            ))}
          </div>

          {filteredNotices.length === 0 && (
            <div className={styles.empty}>
              조건에 맞는 공지사항이 없습니다.
            </div>
          )}

          <section className={styles.filterPanel}>
            <div className={styles.filterHeader}>
              <div>
                <h2>공지사항 맞춤 필터</h2>
                <p>나에게 맞는 공지사항을 선택해 보세요.</p>
              </div>
              <div className={styles.filterActions}>
                {userProfile && (
                  <button onClick={applyProfile}>
                    내 프로필 적용
                  </button>
                )}
                <button onClick={resetFilters}>초기화</button>
              </div>
            </div>

            {filtersDisabled && (
              <p className={styles.description}>
                전체 공지 및 북마크에서는 검색만 적용됩니다.
              </p>
            )}

            <div className={styles.filters}>
              <label>
                캠퍼스
                <select
                  value={selectedCampus}
                  disabled={filtersDisabled}
                  onChange={(event) => setCampus(event.target.value)}
                >
                  <option>전체</option>
                  <option>죽전캠퍼스</option>
                  <option>천안캠퍼스</option>
                </select>
              </label>

              <label>
                학과
                <select
                  value={selectedDepartment}
                  disabled={filtersDisabled}
                  onChange={(event) => setDepartment(event.target.value)}
                >
                  <option>전체</option>
                  {userProfile && <option>내 전공</option>}
                  {departmentOptions.map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>

              <label>
                학년
                <select
                  value={selectedGrade}
                  disabled={filtersDisabled}
                  onChange={(event) => setGrade(event.target.value)}
                >
                  <option>전체</option>
                  <option>1학년</option>
                  <option>2학년</option>
                  <option>3학년</option>
                  <option>4학년</option>
                </select>
              </label>

              <label>
                관심 분야
                <select
                  value={selectedCategory}
                  disabled={filtersDisabled}
                  onChange={(event) => setCategory(event.target.value)}
                >
                  <option>전체</option>
                  {interests.length > 0 && (
                    <option>내 관심 분야</option>
                  )}
                  {categories.map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>

              <label>
                거주 방식
                <select
                  value={selectedResidence}
                  disabled={filtersDisabled}
                  onChange={(event) => setResidence(event.target.value)}
                >
                  <option>전체</option>
                  <option>기숙사</option>
                  <option>자취</option>
                  <option>통학</option>
                </select>
              </label>
            </div>
          </section>

          <footer className={styles.footer}>
            공사다잡 · 공지사항 다 잡아
            <br />
            단국대학교 인공지능융합플랫폼 프로젝트
          </footer>
        </section>
      </main>
    </div>
  );
}
