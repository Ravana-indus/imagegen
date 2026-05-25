import Link from "next/link";

export default function HomePage() {
  return (
    <main className="hero">
      <p className="eyebrow">Brand Studio</p>
      <h1>Product Creative Generator</h1>
      <p className="lede">
        Create polished single images or consistent campaign batches with
        controlled brand overlays.
      </p>
      <Link className="primary-link" href="/dashboard">
        Open dashboard
      </Link>
    </main>
  );
}
