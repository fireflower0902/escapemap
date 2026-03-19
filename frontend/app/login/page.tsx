"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { signInWithPopup, UserCredential } from "firebase/auth";
import { auth, googleProvider } from "@/lib/firebase";
import { useAuth } from "@/contexts/AuthContext";
import TermsModal from "@/components/TermsModal";

// Google 로고 SVG
function GoogleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  );
}

export default function LoginPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  // 약관 모달: 신규 가입자에게만 표시
  const [pendingCredential, setPendingCredential] = useState<UserCredential | null>(null);

  // 이미 로그인된 경우 홈으로
  useEffect(() => {
    if (!loading && user) router.replace("/");
  }, [user, loading, router]);

  async function handleGoogleLogin() {
    setIsLoading(true);
    setError("");
    try {
      const result = await signInWithPopup(auth, googleProvider);
      const isNew = (result as any)._tokenResponse?.isNewUser ?? false;

      if (isNew) {
        // 신규 가입자 → 약관 동의 모달 표시 후 대기
        setPendingCredential(result);
      } else {
        // 기존 유저 → 바로 홈으로
        await syncUserToBackend(result);
        router.replace("/");
      }
    } catch (e: any) {
      if (e.code !== "auth/popup-closed-by-user") {
        setError("로그인 중 오류가 발생했습니다. 다시 시도해 주세요.");
      }
    } finally {
      setIsLoading(false);
    }
  }

  async function handleTermsAccept() {
    if (!pendingCredential) return;
    try {
      await syncUserToBackend(pendingCredential);
      router.replace("/");
    } catch {
      setError("계정 등록 중 오류가 발생했습니다. 다시 시도해 주세요.");
      setPendingCredential(null);
    }
  }

  async function handleTermsCancel() {
    // 약관 거부 → Firebase 로그아웃 후 모달 닫기
    await auth.signOut();
    setPendingCredential(null);
  }

  async function syncUserToBackend(credential: UserCredential) {
    const token = await credential.user.getIdToken();
    await fetch("/api/v1/auth/me", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
  }

  if (loading) return null;

  return (
    <>
      {/* 약관 동의 모달 (신규 가입자만) */}
      {pendingCredential && (
        <TermsModal onAccept={handleTermsAccept} onCancel={handleTermsCancel} />
      )}

      <div className="min-h-[calc(100vh-8rem)] flex items-center justify-center px-4">
        <div className="w-full max-w-sm">

          {/* 타이틀 */}
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-stone-900 mb-2">시작하기</h1>
            <p className="text-stone-500 text-sm">
              로그인하고 빈자리 알림을 받아보세요
            </p>
          </div>

          {/* 카드 */}
          <div className="bg-white rounded-2xl shadow-lg border border-stone-100 p-6 space-y-3">

            {/* 구글 로그인 */}
            <button
              onClick={handleGoogleLogin}
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-3
                         py-3 px-4 rounded-xl border border-stone-200
                         bg-white hover:bg-stone-50 active:scale-[0.98]
                         text-stone-700 font-medium text-sm
                         transition-all duration-150 disabled:opacity-50
                         shadow-sm hover:shadow"
            >
              <GoogleIcon />
              {isLoading ? "로그인 중..." : "구글로 시작하기"}
            </button>

            {/* 에러 메시지 */}
            {error && (
              <p className="text-xs text-red-500 text-center pt-1">{error}</p>
            )}
          </div>

          {/* 하단 안내 */}
          <p className="text-center text-xs text-stone-400 mt-5 leading-relaxed">
            처음 가입 시 이용약관 및 개인정보처리방침 동의가 필요합니다.
          </p>
        </div>
      </div>
    </>
  );
}
