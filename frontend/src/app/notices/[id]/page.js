
import { notFound } from "next/navigation";
import { notices } from "../../noticeData";
import NoticeDetail from "./NoticeDetail";

export function generateStaticParams() {
  return notices.map((notice) => ({
    id: String(notice.id),
  }));
}

export default async function NoticePage({ params }) {
  const { id } = await params;

  const notice = notices.find(
    (item) => String(item.id) === id
  );

  if (!notice) {
    notFound();
  }

  return <NoticeDetail notice={notice} />;
}
