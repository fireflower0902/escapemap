/**
 * Firebase Admin SDK 초기화 (서버 전용 — Route Handler / Server Component에서만 사용)
 *
 * 환경변수:
 *   FIREBASE_SERVICE_ACCOUNT_JSON  — Firebase 서비스 계정 JSON 전체 내용 (문자열)
 *
 * Vercel에서는 Project Settings → Environment Variables 에 위 변수를 추가하세요.
 */
import { initializeApp, getApps, cert } from "firebase-admin/app";
import { getFirestore } from "firebase-admin/firestore";

function initFirebase() {
  if (getApps().length > 0) return;
  const json = process.env.FIREBASE_SERVICE_ACCOUNT_JSON;
  if (!json) throw new Error("FIREBASE_SERVICE_ACCOUNT_JSON 환경변수가 설정되지 않았습니다.");
  initializeApp({ credential: cert(JSON.parse(json)) });
}

export function getDb() {
  initFirebase();
  return getFirestore();
}
