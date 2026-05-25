"use client";

import Link from "next/link";

export function AppHeader() {
  return (
    <header className="app-header">
      <Link className="brand" href="/dashboard">
        Brand Studio
      </Link>
      <nav>
        <Link href="/dashboard">Projects</Link>
        <Link href="/images">Generated images</Link>
        <Link href="/projects/new">New creative</Link>
      </nav>
    </header>
  );
}
