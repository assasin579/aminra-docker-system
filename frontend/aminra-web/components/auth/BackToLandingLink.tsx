import Link from "next/link";

type BackToLandingLinkProps = {
  href?: string;
  label?: string;
};

export function BackToLandingLink({
  href = "/landing",
  label = "Về trang chủ",
}: BackToLandingLinkProps) {
  return (
    <Link
      href={href}
      aria-label={label}
      data-auth-exit="landing"
      className="inline-flex min-h-[40px] items-center gap-2 rounded-full px-3 text-sm font-medium transition-colors hover:bg-white/70 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0A1F44]/30"
      style={{ color: "#0A1F44" }}
    >
      <span aria-hidden="true">←</span>
      <span>{label}</span>
    </Link>
  );
}
