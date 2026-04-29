"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-6">
      <div
        className="w-16 h-16 rounded-full grid place-items-center mb-4"
        style={{
          background: "rgba(239,68,68,0.1)",
          border: "1px solid rgba(239,68,68,0.3)",
        }}
      >
        <svg
          className="w-8 h-8"
          style={{ color: "#f87171" }}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.5"
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
          />
        </svg>
      </div>
      <h2 className="text-lg font-bold text-white mb-2">Đã xảy ra lỗi</h2>
      <p className="text-sm mb-4" style={{ color: "#94a3b8" }}>
        {error.message || "Trang không thể tải. Vui lòng thử lại."}
      </p>
      <button
        onClick={reset}
        className="px-6 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:scale-105"
        style={{ background: "#16a34a" }}
      >
        Thử lại
      </button>
    </div>
  );
}
