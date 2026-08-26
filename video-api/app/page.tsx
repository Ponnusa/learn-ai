import Link from "next/link";

export default function HomePage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-24">
      <p className="text-sm font-mono mb-4" style={{ color: "var(--accent-ink)" }}>
        Developer API · beta
      </p>
      <h1 className="text-4xl font-semibold tracking-tight mb-6" style={{ textWrap: "balance" }}>
        Generate AI, multi-modal educational videos — on demand, in your own product.
      </h1>
      <p className="text-lg mb-10 max-w-2xl" style={{ color: "var(--text-soft)" }}>
        Send a topic, get back a fully narrated lesson video — Manim-animated derivations,
        AI-generated diagrams, and composited video, all rendered from a single API call.
        Not a stock library: every video is generated for the exact topic you ask for.
      </p>

      <div className="flex gap-3 mb-16">
        <Link
          href="/signup"
          className="px-5 py-2.5 rounded-lg font-medium"
          style={{ background: "var(--accent)", color: "#04201C" }}
        >
          Request access
        </Link>
        <Link
          href="/docs"
          className="px-5 py-2.5 rounded-lg font-medium border"
          style={{ borderColor: "var(--border)", color: "var(--text)" }}
        >
          View the docs
        </Link>
      </div>

      <div className="grid sm:grid-cols-3 gap-4">
        {[
          {
            title: "Multi-modal rendering",
            body: "Manim animations for math/physics/chemistry derivations, AI-generated diagrams for everything else, composited into one lesson.",
          },
          {
            title: "Narrated, multi-language",
            body: "A single consistent narrator voice across the whole lesson, in English, Finnish, Swedish, Spanish, French, or Norwegian.",
          },
          {
            title: "Approved, then usable",
            body: "Request a key with a short use-case note. A human reviews it before it can generate anything — no self-serve spam.",
          },
        ].map((f) => (
          <div
            key={f.title}
            className="rounded-xl border p-5"
            style={{ borderColor: "var(--border)", background: "var(--surface)" }}
          >
            <h3 className="font-medium mb-2">{f.title}</h3>
            <p className="text-sm" style={{ color: "var(--text-soft)" }}>
              {f.body}
            </p>
          </div>
        ))}
      </div>

      <p className="text-xs mt-16" style={{ color: "var(--text-faint)" }}>
        Currently in beta — accounts are capped at one generated video while we scale up capacity.
      </p>
    </div>
  );
}
