
"use client";

import { useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import styles from "../login/login.module.css";
import profile from "./onboarding.module.css";

const interests = [
  "학사",
  "장학",
  "행사",
  "기숙사",
  "취업",
  "봉사",
  "학생복지",
  "공모전",
];

const PROFILE_KEY = "gonsadajob_profile";

function subscribe(callback) {
  window.addEventListener("storage", callback);
  window.addEventListener("gonsadajob-change", callback);

  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("gonsadajob-change", callback);
  };
}

function getSnapshot() {
  try {
    return localStorage.getItem(PROFILE_KEY);
  } catch {
    return null;
  }
}

function getServerSnapshot() {
  return null;
}

function parseProfile(value) {
  try {
    const data = JSON.parse(value);
    return data && typeof data === "object" ? data : {};
  } catch {
    return {};
  }
}

export default function ProfileForm({ isSettings = false }) {
  const router = useRouter();
  const [message, setMessage] = useState("");

  const rawProfile = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot
  );

  const savedProfile = parseProfile(rawProfile);

  const savedInterests = Array.isArray(savedProfile.interests)
    ? savedProfile.interests
    : [];

  function handleSave(event) {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);

    const userProfile = {
      university: "단국대학교",
      campus: formData.get("campus"),
      department: formData.get("department").trim(),
      doubleMajor: formData.get("doubleMajor").trim(),
      grade: formData.get("grade"),
      interests: formData.getAll("interests"),
      residence: formData.get("residence"),
    };

    if (!userProfile.department) {
      setMessage("주전공 학과를 입력해 주세요.");
      return;
    }

    try {
      localStorage.setItem(
        PROFILE_KEY,
        JSON.stringify(userProfile)
      );

      window.dispatchEvent(
        new Event("gonsadajob-change")
      );

      window.dispatchEvent(new Event("storage"));

      router.push("/");
    } catch {
      setMessage("프로필 저장에 실패했습니다.");
    }
  }

  function handleReset() {
    const confirmed = window.confirm(
      "개인화 프로필을 초기화하시겠습니까?"
    );

    if (!confirmed) return;

    try {
      localStorage.removeItem(PROFILE_KEY);

      window.dispatchEvent(
        new Event("gonsadajob-change")
      );

      window.dispatchEvent(new Event("storage"));

      router.push("/");
    } catch {
      setMessage("프로필 초기화에 실패했습니다.");
    }
  }

  return (
    <main className={styles.page}>
      <div
        className={styles.card}
        style={{ maxWidth: "650px" }}
      >
        <Link href="/" className={styles.brand}>
          <div className={styles.logo}>✓</div>
          <h1>공사다잡</h1>
          <p>공지사항 다 잡아</p>
        </Link>

        <div className={styles.school}>
          단국대학교 공지사항 개인화 서비스
        </div>

        <div className={styles.heading}>
          <h2>
            {isSettings
              ? "마이페이지"
              : "나에게 맞는 공지 찾기"}
          </h2>

          <p>
            {isSettings
              ? "나의 대학생활 정보와 관심 분야를 관리하세요."
              : "나의 대학생활 정보를 설정하고 맞춤 공지사항을 확인하세요."}
          </p>
        </div>

        {isSettings && (
          <div
            className={profile.info}
            style={{ marginBottom: "24px" }}
          >
            <strong>
              {rawProfile
                ? "개인화 프로필 설정 완료"
                : "아직 설정된 프로필이 없습니다."}
            </strong>

            {rawProfile && (
              <>
                <p style={{ marginTop: "8px" }}>
                  단국대학교 {savedProfile.campus}
                </p>
                <p>
                  {savedProfile.department}
                  {savedProfile.doubleMajor
                    ? ` / ${savedProfile.doubleMajor}`
                    : ""}
                </p>
                <p>
                  {savedProfile.grade} · {savedProfile.residence}
                </p>
              </>
            )}
          </div>
        )}

        <form
          key={rawProfile || "empty"}
          className={styles.form}
          onSubmit={handleSave}
        >
          <label className={styles.field}>
            소속 대학교
            <input
              type="text"
              value="단국대학교"
              readOnly
            />
          </label>

          <fieldset className={profile.group}>
            <legend>소속 캠퍼스</legend>

            <div className={profile.twoColumns}>
              {["죽전캠퍼스", "천안캠퍼스"].map(
                (campus) => (
                  <label
                    key={campus}
                    className={profile.option}
                  >
                    <input
                      type="radio"
                      name="campus"
                      value={campus}
                      defaultChecked={
                        savedProfile.campus === campus
                      }
                      required
                    />
                    <span>{campus}</span>
                  </label>
                )
              )}
            </div>
          </fieldset>

          <label className={styles.field}>
            주전공
            <input
              type="text"
              name="department"
              defaultValue={savedProfile.department || ""}
              placeholder="예: 소프트웨어학과"
              required
            />
          </label>

          <label className={styles.field}>
            복수전공 (선택)
            <input
              type="text"
              name="doubleMajor"
              defaultValue={savedProfile.doubleMajor || ""}
              placeholder="복수전공 학과명을 입력해 주세요"
            />
          </label>

          <label className={styles.field}>
            학년
            <select
              name="grade"
              className={profile.select}
              defaultValue={savedProfile.grade || ""}
              required
            >
              <option value="" disabled>
                학년을 선택해 주세요
              </option>
              <option value="1학년">1학년</option>
              <option value="2학년">2학년</option>
              <option value="3학년">3학년</option>
              <option value="4학년">4학년</option>
            </select>
          </label>

          <fieldset className={profile.group}>
            <legend>관심 분야</legend>

            <p className={profile.help}>
              관심 있는 분야를 여러 개 선택할 수 있습니다.
              선택하지 않으면 전체 분야를 대상으로 합니다.
            </p>

            <div className={profile.interestGrid}>
              {interests.map((interest) => (
                <label
                  key={interest}
                  className={profile.option}
                >
                  <input
                    type="checkbox"
                    name="interests"
                    value={interest}
                    defaultChecked={
                      savedInterests.includes(interest)
                    }
                  />
                  <span>{interest}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className={profile.group}>
            <legend>거주 방식</legend>

            <div className={profile.threeColumns}>
              {["기숙사", "자취", "통학"].map(
                (residence) => (
                  <label
                    key={residence}
                    className={profile.option}
                  >
                    <input
                      type="radio"
                      name="residence"
                      value={residence}
                      defaultChecked={
                        savedProfile.residence === residence
                      }
                      required
                    />
                    <span>{residence}</span>
                  </label>
                )
              )}
            </div>
          </fieldset>

          <div className={profile.info}>
            현재는 프로토타입입니다.
            개인화 설정은 이 브라우저에 저장되며,
            실제 회원 정보 및 데이터베이스 연동은
            추후 제공됩니다.
          </div>

          <button
            type="submit"
            className={styles.submit}
          >
            {isSettings
              ? "변경 사항 저장"
              : "맞춤 공지 시작하기 →"}
          </button>

          {isSettings && rawProfile && (
            <button
              type="button"
              onClick={handleReset}
              style={{
                padding: "13px",
                border: "1px solid #f1c5c9",
                borderRadius: "9px",
                background: "#fff5f5",
                color: "#dc5262",
                fontSize: "13px",
              }}
            >
              개인화 프로필 초기화
            </button>
          )}

          {message && (
            <p
              className={styles.message}
              role="alert"
            >
              {message}
            </p>
          )}
        </form>

        <Link href="/" className={styles.back}>
          ← 메인 화면으로 돌아가기
        </Link>
      </div>

      <footer className={styles.footer}>
        공사다잡 · 단국대학교 인공지능융합플랫폼 프로젝트
      </footer>
    </main>
  );
}
