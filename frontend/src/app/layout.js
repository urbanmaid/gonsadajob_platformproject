
import "./globals.css";

export const metadata = {
  title: "공사다잡 - 공지사항 다 잡아",
  description: "대학생을 위한 AI 기반 공지사항 개인화 플랫폼",
};

export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
