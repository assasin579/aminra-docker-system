import Link from "next/link";

/** Route-backed tabs keep existing dossier links and browser history usable. */
export default function DocumentWorkspaceTabs({ active }: { active: "documents" | "dossiers" }) {
  return (
    <nav aria-label="Kho tài liệu" data-document-workspace className="grid grid-cols-2 gap-1.5 rounded-2xl border border-slate-200 bg-slate-50 p-1.5 mb-6">
      {([
        { key: "documents", href: "/documents", label: "Tài liệu DN" },
        { key: "dossiers", href: "/dossiers", label: "Các bộ hồ sơ" },
      ] as const).map(tab => (
        <Link key={tab.key} href={tab.href} aria-current={active === tab.key ? "page" : undefined}
          className={`rounded-xl px-3 py-3 text-center text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 ${active === tab.key ? "bg-white text-navy-900 shadow-sm ring-1 ring-slate-200" : "text-slate-500 hover:bg-white hover:text-navy-900"}`}>
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}
