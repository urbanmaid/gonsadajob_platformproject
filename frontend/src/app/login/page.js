
"use client";

import { useState } from "react";
import Link from "next/link";
import styles from "./login.module.css";

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("");

  function handleLogin(event) {
    event.preventDefault();

    // 추후 백엔드 로그인 API 연동
    setMessage(
      "현재는 UI 테스트 단계입니다. 실제 로그인은 서버 연동 후 이용할 수 있습니다."
    );
  }

  return (
    <main className={styles.page}>
      <div className={styles.card}>
        <Link href="/" className={styles.brand}>
          <div className={styles.logo}>✓</div>
          <h1>공사다잡</h1>
          <p>공지사항 다 잡아</p>
        </Link>

        <div className={styles.school}>
          단국대학교 공지사항 개인화 서비스
        </div>

        <div className={styles.heading}>
          <h2>로그인</h2>
          <p>
            나에게 필요한 학교 소식을 만나보세요.
          </p>
        </div>

        <form
          className={styles.form}
          onSubmit={handleLogin}
        >
          <label className={styles.field}>
            이메일
            <input
              type="email"
              name="email"
              placeholder="이메일을 입력해 주세요"
              autoComplete="email"
              required
            />
          </label>

          <div className={styles.field}>
            <label htmlFor="password">
              비밀번호
            </label>

            <div className={styles.passwordBox}>
              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                placeholder="비밀번호를 입력해 주세요"
                autoComplete="current-password"
                required
              />

              <button
                type="button"
                className={styles.toggle}
                onClick={() =>
                  setShowPassword(!showPassword)
                }
              >
                {showPassword ? "숨기기" : "보기"}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className={styles.submit}
          >
            로그인
          </button>

          {message && (
            <p
              className={styles.message}
              role="status"
            >
              {message}
            </p>
          )}
        </form>

        <div className={styles.signup}>
          아직 계정이 없으신가요?
          <Link href="/register">
            회원가입
          </Link>
        </div>

        <Link
          href="/"
          className={styles.back}
        >
          ← 메인 화면으로 돌아가기
        </Link>
      </div>

      <footer className={styles.footer}>
        공사다잡 · 인공지능융합플랫폼 프로젝트
      </footer>
    </main>
  );
}
