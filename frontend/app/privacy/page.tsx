import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export const metadata = {
  title: 'Privacy Policy · LearnX-AI',
};

function Section({ num, title, children }: { num: string; title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-[var(--tx1)] font-semibold text-base flex items-baseline gap-2">
        <span className="text-[var(--tx7)] font-normal text-sm w-6 shrink-0">{num}.</span>
        {title}
      </h2>
      <div className="text-[var(--tx3)] text-sm leading-relaxed space-y-2.5 pl-7">
        {children}
      </div>
    </section>
  );
}

function DataTable({ rows }: { rows: [string, string][] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--bd)]">
      <table className="w-full text-sm">
        <tbody>
          {rows.map(([label, value], i) => (
            <tr key={i} className="border-b border-[var(--bd)] last:border-0">
              <td className="px-4 py-2.5 font-medium text-[var(--tx2)] align-top w-48 bg-[var(--surface)] shrink-0 whitespace-nowrap">{label}</td>
              <td className="px-4 py-2.5 text-[var(--tx4)]">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--tx1)]">
      <div className="sticky top-0 z-10 border-b border-[var(--bd)] bg-[var(--surface)]/80 backdrop-blur-sm">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 h-12 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-1.5 text-sm text-[var(--tx5)] hover:text-[var(--tx1)] transition-colors">
            <ArrowLeft size={14} /> Back to app
          </Link>
          <div className="flex items-center gap-2">
            <img src="/logo-36.png" alt="LearnX-AI" className="w-5 h-5 object-contain" />
            <span className="text-[var(--tx6)] text-xs">learnx-ai.com</span>
          </div>
        </div>
      </div>

      <main className="max-w-2xl mx-auto px-4 sm:px-6 py-12">
        <header className="mb-10">
          <p className="text-xs uppercase tracking-widest text-[var(--tx7)] font-medium mb-2">Legal</p>
          <h1 className="text-3xl font-bold text-[var(--tx1)] mb-2">Privacy Policy</h1>
          <p className="text-[var(--tx6)] text-sm">Last updated: 15 April 2026</p>
        </header>

        <div className="space-y-8">
          <Section num="1" title="Data Controller">
            <p>The data controller for LearnX-AI is:</p>
            <DataTable rows={[
              ['Company', 'NordX Labs Oy'],
              ['Business ID (Y-tunnus)', '3615236-4'],
              ['Email', 'hello@animlearn.com'],
            ]} />
          </Section>

          <Section num="2" title="What Data We Collect">
            <DataTable rows={[
              ['Account', 'Full name, email address, preferred language, account creation date'],
              ['Google Sign-In (optional)', 'Google user ID, profile picture URL, name and email from Google OAuth'],
              ['Learning activity', 'Video watch percentage, concept mastery scores, practice attempts and answers, AI feedback on submissions, time taken on exercises'],
              ['Chat history', 'Problem-solving conversations with the AI tutor (Pixel AI)'],
              ['Security logs', 'IP address, browser user-agent — recorded on sign-in/sign-up for fraud prevention. Retained for 90 days, then deleted automatically.'],
            ]} />
          </Section>

          <Section num="3" title="Legal Basis for Processing">
            <p>Processing of personal data in LearnX-AI is based on public interest and the exercise of official authority (GDPR Article 6(1)(e)), in connection with the school's educational activities.</p>
            <p>Security logging (IP address, user-agent) is based on our legitimate interest (Article 6(1)(f)) in preventing unauthorised access and fraud.</p>
          </Section>

          <Section num="4" title="Profiling and Automated Processing">
            <p>LearnX-AI automatically analyses your learning activity to personalise the educational experience. This includes:</p>
            <ul className="list-disc list-inside space-y-1 text-[var(--tx4)]">
              <li>Calculating a mastery score (0–1) per concept based on your quiz answers and practice attempts</li>
              <li>Tracking a learning trend (improving / stable / declining) per concept</li>
              <li>Monitoring video watch completion to identify gaps in learning</li>
              <li>Generating personalised practice questions based on your performance</li>
            </ul>
            <p>This constitutes profiling under GDPR Article 4(4). The profiling is carried out in the public interest as part of educational activities. It does not produce legal effects or significantly affect you.</p>
          </Section>

          <Section num="5" title="Third-Party Processors">
            <p>We share data with the following third-party service providers acting as data processors:</p>
            <DataTable rows={[
              ['Google LLC', 'Google OAuth authentication. Data transferred: name, email, Google user ID. Governed by Google\'s Data Processing Terms.'],
              ['Anthropic / Claude (via Google Cloud Vertex AI, EU)', 'AI content generation. Learning prompts and concept content are processed by Claude, hosted on Google Cloud infrastructure within the European Union. No student personal identifiers are sent to the model.'],
              ['Microsoft Azure (EU)', 'AI embeddings for syllabus search (Azure OpenAI). Document text is processed. Hosted in EU region.'],
              ['Cloudflare R2 (EU)', 'Storage of generated video files and SVG assets.'],
              ['Supabase / PostgreSQL', 'Database hosting for all user and learning data.'],
            ]} />
            <p>We do not sell personal data to any third party.</p>
          </Section>

          <Section num="6" title="Data Retention">
            <DataTable rows={[
              ['Account data', 'Retained while your account is active. Deleted on account deletion request.'],
              ['Learning activity', 'Retained while your account is active. Deleted on account deletion.'],
              ['Security logs (IP, user-agent)', 'Automatically deleted after 90 days.'],
              ['AI-generated videos', 'Retained while linked to your account. Deleted on account deletion.'],
            ]} />
          </Section>

          <Section num="7" title="Your Rights">
            <p>Under GDPR, you have the following rights:</p>
            <ul className="space-y-1.5">
              {[
                ['Right of access', 'request a copy of your personal data'],
                ['Right to rectification', 'correct inaccurate data via Settings'],
                ['Right to erasure', 'delete your account and all associated data via Settings → Delete Account'],
                ['Right to restriction', 'request that we limit processing of your data'],
                ['Right to object', 'object to processing based on public interest'],
                ['Right to data portability', 'request your data in a machine-readable format'],
              ].map(([right, desc]) => (
                <li key={right} className="flex gap-1.5 flex-wrap">
                  <span className="font-medium text-[var(--tx2)]">{right}</span>
                  <span className="text-[var(--tx5)]">— {desc}</span>
                </li>
              ))}
            </ul>
            <p>To exercise any of these rights, contact us at <a href="mailto:hello@animlearn.com" className="text-purple-400 hover:underline">hello@animlearn.com</a>. We will respond within 30 days.</p>
            <p>You also have the right to lodge a complaint with the Finnish Data Protection Ombudsman (tietosuoja.fi).</p>
          </Section>

          <Section num="8" title="Data Security">
            <p>We implement the following security measures:</p>
            <ul className="list-disc list-inside space-y-1 text-[var(--tx4)]">
              <li>Passwords are hashed using bcrypt (never stored in plaintext)</li>
              <li>All data in transit is encrypted with TLS/HTTPS</li>
              <li>Authentication tokens are stored locally in the browser and not sent to third parties</li>
              <li>Access to production databases is restricted to authorised personnel</li>
            </ul>
          </Section>

          <Section num="9" title="Cookies and Local Storage">
            <p>LearnX-AI does not use tracking cookies. Authentication tokens are stored in your browser's localStorage and are used only to keep you logged in. No third-party analytics or advertising cookies are used.</p>
          </Section>

          <Section num="10" title="Children's Data">
            <p>LearnX-AI is designed for use in schools, including by minors. Student accounts are created and managed within the school context. Teachers and school administrators are responsible for ensuring that student accounts comply with applicable laws on processing children's data.</p>
            <p>We do not knowingly collect data from children outside of a supervised educational context.</p>
          </Section>

          <Section num="11" title="Changes to This Policy">
            <p>We may update this privacy policy from time to time. When we do, we will update the "Last updated" date at the top of this page. Material changes will be communicated via the application or by email.</p>
          </Section>

          <Section num="12" title="Contact">
            <DataTable rows={[
              ['Company', 'NordX Labs Oy'],
              ['Email', 'hello@animlearn.com'],
            ]} />
          </Section>
        </div>
      </main>

      <footer className="border-t border-[var(--bd)] py-8 mt-12">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center gap-4 justify-between">
          <div className="flex items-center gap-2">
            <img src="/logo-36.png" alt="LearnX-AI" className="w-5 h-5 object-contain" />
            <span className="text-[var(--tx6)] text-xs">NordX Labs Oy · Business ID: 3615236-4 · Espoo, Finland</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/privacy" className="text-purple-400 text-xs">Privacy Policy</Link>
            <Link href="/terms" className="text-[var(--tx6)] hover:text-[var(--tx1)] text-xs transition-colors">Terms of Service</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
