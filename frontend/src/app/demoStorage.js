
"use client";

import { useSyncExternalStore } from "react";

export const initialTasks = [
  {
    id: "notice-1",
    title: "장학금 신청 서류 준비",
    date: "12.10",
    done: false,
  },
  {
    id: "notice-2",
    title: "세미나 참가 신청서 제출",
    date: "12.05",
    done: false,
  },
  {
    id: "notice-4",
    title: "기말고사 일정 확인",
    date: "12.03",
    done: false,
  },
  {
    id: "notice-6",
    title: "공모전 신청 자격 확인",
    date: "12.15",
    done: false,
  },
];

export const BOOKMARK_KEY = "gonsadajob_bookmarks";
export const TASK_KEY = "gonsadajob_tasks";

// 페이지 및 브라우저 탭 사이의 데이터 변경 감지
function subscribe(callback) {
  window.addEventListener("storage", callback);
  window.addEventListener("gonsadajob-change", callback);

  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("gonsadajob-change", callback);
  };
}

function readStorage(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function parseList(value, fallback) {
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function getServerSnapshot() {
  return null;
}

// 공통 데이터 저장 및 불러오기 기능
export function useDemoList(key, fallback = []) {
  const raw = useSyncExternalStore(
    subscribe,
    () => readStorage(key),
    getServerSnapshot
  );

  const items = parseList(raw, fallback);

  function updateItems(update) {
    try {
      const current = parseList(
        localStorage.getItem(key),
        fallback
      );

      const next =
        typeof update === "function"
          ? update(current)
          : update;

      localStorage.setItem(key, JSON.stringify(next));

      window.dispatchEvent(
        new Event("gonsadajob-change")
      );
    } catch {
      alert("데이터를 저장하지 못했습니다.");
    }
  }

  return [items, updateItems];
}
