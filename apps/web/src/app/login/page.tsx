import Link from "next/link";
import { LoginForm } from "@/components/LoginForm";

export default function LoginPage() {
  return (
    <main className="auth-page">
      <Link className="brand" href="/">
        Brand Studio
      </Link>
      <section className="auth-panel">
        <p className="eyebrow">Administrator</p>
        <h1>Sign in</h1>
        <p className="lede">Access generation projects and saved exports.</p>
        <LoginForm />
      </section>
    </main>
  );
}
