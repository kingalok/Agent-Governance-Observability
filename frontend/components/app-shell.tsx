import Link from "next/link";
import { ReactNode } from "react";

const navigation = [
  { href: "/", label: "Overview" },
  { href: "/agents", label: "Agent Registry" },
  { href: "/runs", label: "Run Explorer" },
  { href: "/approvals", label: "Approval Queue" },
];

export function AppShell({
  children,
  title,
  subtitle,
}: {
  children: ReactNode;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="dashboard-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <p className="brand-kicker">CTO Demo</p>
          <h1>Agent Governance Observatory</h1>
          <p className="sidebar-copy">
            Enterprise controls for approvals, policy checks, and operational visibility.
          </p>
        </div>
        <nav className="sidebar-nav">
          {navigation.map((item) => (
            <Link key={item.href} href={item.href} className="nav-link">
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="dashboard-main">
        <header className="page-header">
          <div>
            <p className="eyebrow">Agent Governance PoC</p>
            <h2>{title}</h2>
          </div>
          <p className="page-subtitle">{subtitle}</p>
        </header>
        {children}
      </main>
    </div>
  );
}
