"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiRequest } from "@/lib/api";

export function AppHeader() {
  const router = useRouter();

  async function signOut() {
    await apiRequest("/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="app-header">
      <Link className="brand" href="/dashboard">
        Brand Studio
      </Link>
      <nav>
        <Link href="/projects/new">New creative</Link>
        <button type="button" className="text-button" onClick={signOut}>
          Sign out
        </button>
      </nav>
    </header>
  );
}
