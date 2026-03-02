"use client";

import { useState } from "react";
import { X, Bell, Mail, MessageSquare, Check } from "lucide-react";

type AlertModalProps = {
  isOpen: boolean;
  onClose: () => void;
  themeName: string;
  themeId: number;
  date: string;
  timeSlot: string;
};

export default function AlertModal({
  isOpen,
  onClose,
  themeName,
  themeId,
  date,
  timeSlot,
}: AlertModalProps) {
  const [email, setEmail] = useState("");
  const [channel, setChannel] = useState<"email" | "kakao">("email");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);

    // TODO: 실제 API 호출로 교체
    // await fetch('/api/v1/alerts', { method: 'POST', body: JSON.stringify({...}) })
    await new Promise((r) => setTimeout(r, 800)); // 임시 딜레이

    setSubmitted(true);
    setLoading(false);
  }

  return (
    /* 배경 오버레이 */
    <div
      className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden">

        {/* 모달 헤더 */}
        <div className="bg-gradient-to-r from-brand-400 to-amber-400 p-6 relative">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-1.5 rounded-full bg-white/30
                       hover:bg-white/50 transition-colors"
          >
            <X size={18} className="text-stone-800" />
          </button>
          <div className="text-4xl mb-2">🔔</div>
          <h2 className="text-xl font-extrabold text-stone-900">
            빈자리 알림 등록
          </h2>
          <p className="text-stone-700 text-sm mt-1">
            자리가 나면 바로 알려드릴게요!
          </p>
        </div>

        {/* 모달 본문 */}
        <div className="p-6">
          {submitted ? (
            /* 등록 완료 화면 */
            <div className="text-center py-6">
              <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Check size={32} className="text-emerald-600" />
              </div>
              <h3 className="text-xl font-bold text-stone-900 mb-2">
                알림 등록 완료!
              </h3>
              <p className="text-stone-500 text-sm mb-2">
                <strong className="text-stone-700">{themeName}</strong> 테마의<br />
                {date} {timeSlot} 빈자리가 나면<br />
                <strong className="text-stone-700">
                  {channel === "email" ? "이메일" : "카카오"}
                </strong>
                로 즉시 알려드립니다.
              </p>
              <button onClick={onClose} className="btn-primary mt-6 w-full">
                확인
              </button>
            </div>
          ) : (
            /* 등록 폼 */
            <form onSubmit={handleSubmit} className="space-y-5">
              {/* 알림 내용 요약 */}
              <div className="bg-brand-50 border border-brand-200 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <span className="text-2xl">🔐</span>
                  <div>
                    <p className="font-bold text-stone-900">{themeName}</p>
                    <p className="text-stone-500 text-sm">
                      {date} · {timeSlot}
                    </p>
                  </div>
                </div>
              </div>

              {/* 알림 채널 선택 */}
              <div>
                <p className="text-sm font-semibold text-stone-700 mb-2">
                  알림 받을 방법
                </p>
                <div className="grid grid-cols-2 gap-3">
                  {(["email", "kakao"] as const).map((ch) => (
                    <button
                      key={ch}
                      type="button"
                      onClick={() => setChannel(ch)}
                      className={`flex items-center gap-2 p-3 rounded-xl border-2 transition-all
                        ${channel === ch
                          ? "border-brand-400 bg-brand-50 text-stone-900"
                          : "border-stone-200 hover:border-stone-300 text-stone-600"
                        }`}
                    >
                      {ch === "email" ? (
                        <Mail size={18} className={channel === ch ? "text-brand-600" : ""} />
                      ) : (
                        <MessageSquare size={18} className={channel === ch ? "text-brand-600" : ""} />
                      )}
                      <span className="font-medium text-sm">
                        {ch === "email" ? "이메일" : "카카오톡"}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              {/* 이메일 입력 */}
              {channel === "email" && (
                <div>
                  <label className="text-sm font-semibold text-stone-700 mb-1.5 block">
                    이메일 주소
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="example@email.com"
                    required
                    className="w-full border-2 border-stone-200 rounded-xl px-4 py-3 text-sm
                               focus:outline-none focus:border-brand-400 transition-colors"
                  />
                </div>
              )}

              {channel === "kakao" && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-sm text-yellow-800">
                  💬 카카오 알림톡은 준비 중입니다. 이메일 알림을 먼저 이용해 주세요.
                </div>
              )}

              <button
                type="submit"
                disabled={loading || channel === "kakao"}
                className="btn-primary w-full flex items-center justify-center gap-2
                           disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <span className="animate-spin w-4 h-4 border-2 border-stone-900 border-t-transparent rounded-full" />
                ) : (
                  <Bell size={18} />
                )}
                {loading ? "등록 중..." : "알림 등록하기"}
              </button>

              <p className="text-xs text-stone-400 text-center">
                빈자리 발생 시 1회 발송 후 자동 해제됩니다.
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
