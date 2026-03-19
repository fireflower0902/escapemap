"use client";

import { useState } from "react";
import { X, ExternalLink } from "lucide-react";

interface TermsModalProps {
  onAccept: () => void;
  onCancel: () => void;
}

export default function TermsModal({ onAccept, onCancel }: TermsModalProps) {
  const [agreed, setAgreed] = useState(false);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6">

        {/* 헤더 */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold text-stone-900">서비스 이용 동의</h2>
          <button
            onClick={onCancel}
            className="p-1.5 rounded-lg hover:bg-stone-100 transition-colors"
          >
            <X size={18} className="text-stone-500" />
          </button>
        </div>

        {/* 안내 문구 */}
        <p className="text-sm text-stone-500 mb-5 leading-relaxed">
          이스케이프맵 서비스를 이용하려면 아래 약관에 동의해 주세요.
        </p>

        {/* 동의 체크박스 */}
        <label className="flex items-start gap-3 cursor-pointer group">
          <input
            type="checkbox"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            className="mt-0.5 w-4 h-4 accent-brand-400 cursor-pointer shrink-0"
          />
          <span className="text-sm text-stone-700 leading-relaxed">
            이용약관 및 개인정보처리방침에 동의합니다.{" "}
            <span className="text-xs text-stone-400">(필수)</span>
          </span>
        </label>

        {/* 약관 확인 링크 */}
        <div className="flex gap-3 mt-3 ml-7">
          <a
            href="/terms"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-700 font-medium transition-colors"
          >
            이용약관 확인
            <ExternalLink size={11} />
          </a>
          <span className="text-stone-300 text-xs">|</span>
          <a
            href="/privacy"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-700 font-medium transition-colors"
          >
            개인정보처리방침 확인
            <ExternalLink size={11} />
          </a>
        </div>

        {/* 버튼 */}
        <div className="flex gap-2 mt-6">
          <button
            onClick={onCancel}
            className="flex-1 py-2.5 rounded-xl border border-stone-200 text-stone-600
                       text-sm font-medium hover:bg-stone-50 transition-colors"
          >
            취소
          </button>
          <button
            onClick={onAccept}
            disabled={!agreed}
            className="flex-1 py-2.5 rounded-xl bg-brand-400 text-stone-900
                       text-sm font-bold transition-all
                       disabled:opacity-40 disabled:cursor-not-allowed
                       hover:bg-brand-500 active:scale-95"
          >
            동의하고 시작하기
          </button>
        </div>
      </div>
    </div>
  );
}
