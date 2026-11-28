
"use client";

import { useState } from "react";
import Link from "next/link";
import styles from "../login/login.module.css";

export default function RegisterPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("");
  const [success, setSuccess] = useState(false);

  function handleRegister(event) {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);
    const name = formData.get("name").trim();
    const password = formData.get("password");
    const confirmPassword = formData.get("confirmPassword");

    setSuccess(false);

    if (!name) {
      setMessage("이름을 입력해 주세요.");
      return;
    }

    if (password.length < 8) {
      setMessage("비밀번호는 8자 이상 입력해 주세요.");
      return;
    }

    if (password !== confirmPassword) {
      setMessage("비밀번호가 일치하지 않습니다.");
      return;
    }

    // 추후 백엔드 회원가입 API 연동
    setSuccess(true);
    setMessage(
      "입력값 검증이 완료되었습니다. 실제 회원가입은 서버 연동 후 가능합니다."
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
          <h2>회원가입</h2>
          <p>나만의 맞춤 공지사항 서비스를 시작하세요.</p>
        </div>

        <form
          className={styles.form}
          onSubmit={handleRegister}
          onChange={() => {
            setMessage("");
            setSuccess(false);
          }}
        >
          <label className={styles.field}>
            이름
            <input
              type="text"
              name="name"
              placeholder="이름을 입력해 주세요"
              autoComplete="name"
              required
            />
          </label>

          <label className={styles.field}>
            소속 대학교
            <input
              type="text"
              value="단국대학교"
              readOnly
            />
          </label>

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
                type={showPassword ? "text" : "password"}
                name="password"
                placeholder="8자 이상 입력해 주세요"
                autoComplete="new-password"
                minLength={8}
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

          <label className={styles.field}>
            비밀번호 확인
            <input
              type={showPassword ? "text" : "password"}
              name="confirmPassword"
              placeholder="비밀번호를 다시 입력해 주세요"
              autoComplete="new-password"
              required
            />
          </label>

          <button
            type="submit"
            className={styles.submit}
          >
            회원가입
          </button>

          {message && (
            <p
              className={styles.message}
              role="status"
              style={{
                color: success ? "#198754" : "#dc5262",
                background: success ? "#e4f6ec" : "#fff1f2",
              }}
            >
                            {message}
            </p>
          )}

          {success && (
            <Link
              href="/onboarding"
              className={styles.submit}
              style={{ textAlign: "center" }}
            >
              개인화 설정 체험하기 →
            </Link>
          )}
        </form>

        <div className={styles.signup}>
          이미 계정이 있으신가요?
          <Link href="/login">로그인</Link>
        </div>

        <Link href="/" className={styles.back}>
          ← 메인 화면으로 돌아가기
        </Link>
      </div>

      <footer className={styles.footer}>
        공사다잡 · 인공지능융합플랫폼 프로젝트
      </footer>
    </main>
  );
}
