"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Viewer" },
  { href: "/capture", label: "Registra" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="flex items-center gap-1 px-6 py-3 border-b border-white/10 bg-black/20">
      <span className="text-sm font-semibold mr-4 text-white/90">3D Builder</span>
      {LINKS.map((link) => {
        const active = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              active
                ? "bg-indigo-500 text-white"
                : "text-white/60 hover:text-white hover:bg-white/10"
            }`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
