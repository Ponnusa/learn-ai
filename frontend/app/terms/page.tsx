import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export const metadata = {
  title: 'Terms of Service · LearnX-AI',
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
              <td className="px-4 py-2.5 font-medium text-[var(--tx2)] align-top bg-[var(--surface)] shrink-0 whitespace-nowrap w-40">{label}</td>
              <td className="px-4 py-2.5 text-[var(--tx4)]">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function TermsOfServicePage() {
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
          <h1 className="text-3xl font-bold text-[var(--tx1)] mb-2">Terms of Service</h1>
          <p className="text-[var(--tx6)] text-sm">Last updated: 15 April 2026</p>
        </header>

        <div className="space-y-8">
          <Section num="1" title="About LearnX-AI">
            <p>LearnX-AI is an AI-powered educational platform that generates animated learning videos and adaptive practice exercises. It is operated by NordX Labs Oy (Business ID: 3615236-4), registered in Finland.</p>
            <p>By accessing or using LearnX-AI, you agree to these Terms of Service. If you are using LearnX-AI as part of a school or institution, your institution may have a separate agreement with us that takes precedence.</p>
          </Section>

          <Section num="2" title="Who Can Use LearnX-AI">
            <p>LearnX-AI is intended for use in educational settings. There are two user roles:</p>
            <ul className="list-disc list-inside space-y-1 text-[var(--tx4)]">
              <li><span className="font-medium text-[var(--tx2)]">Teachers</span> — can upload syllabi, create courses, generate video content, manage assignments, and view student analytics.</li>
              <li><span className="font-medium text-[var(--tx2)]">Students</span> — can watch videos, complete assignments, and practise with adaptive exercises within courses they are enrolled in.</li>
            </ul>
            <p>If you are under 16 years old, you may only use LearnX-AI under the supervision of a teacher or school administrator. Students do not create accounts independently — they are enrolled by teachers.</p>
          </Section>

          <Section num="3" title="Acceptable Use">
            <p>You agree to use LearnX-AI only for lawful educational purposes. You must not:</p>
            <ul className="list-disc list-inside space-y-1 text-[var(--tx4)]">
              <li>Upload content that is illegal, offensive, defamatory, or infringes third-party intellectual property rights</li>
              <li>Attempt to access another user's account or data without authorisation</li>
              <li>Reverse-engineer, scrape, or abuse the LearnX-AI API or infrastructure</li>
              <li>Use LearnX-AI to generate content for commercial resale without written permission</li>
              <li>Enter personal data of third parties (e.g. student names) into AI prompt fields — use anonymised or fictional names in examples</li>
            </ul>
          </Section>

          <Section num="4" title="AI-Generated Content Disclaimer">
            <p>LearnX-AI uses artificial intelligence to generate educational videos, explanations, and practice questions. AI-generated content may contain errors, inaccuracies, or omissions.</p>
            <ul className="list-disc list-inside space-y-1 text-[var(--tx4)]">
              <li>All AI-generated content should be verified against authoritative sources before being used for assessment or grading</li>
              <li>Teachers are responsible for reviewing content before sharing it with students</li>
              <li>LearnX-AI does not guarantee that generated content is accurate, complete, or up to date</li>
              <li>Do not use LearnX-AI as the sole basis for medical, legal, financial, or safety-critical decisions</li>
            </ul>
          </Section>

          <Section num="5" title="Teacher Responsibilities">
            <p>If you are using LearnX-AI as a teacher, you are responsible for:</p>
            <ul className="list-disc list-inside space-y-1 text-[var(--tx4)]">
              <li>Ensuring that student enrolment and data processing comply with your school's data protection policy and applicable law</li>
              <li>Reviewing AI-generated video content for accuracy before making it available to students</li>
              <li>Not uploading copyrighted content in a way that violates the publisher's terms</li>
              <li>Managing course access and ensuring only enrolled students can access course material</li>
            </ul>
          </Section>

          <Section num="6" title="Intellectual Property">
            <p><span className="font-medium text-[var(--tx2)]">Your content:</span> You retain ownership of the syllabi, documents, and prompts you upload. By uploading content, you grant NordX Labs Oy a limited licence to process and store that content for the purpose of providing the service.</p>
            <p><span className="font-medium text-[var(--tx2)]">Generated content:</span> AI-generated videos and materials may be used by you for educational purposes. You may not resell or commercially distribute generated content without our prior written consent.</p>
            <p><span className="font-medium text-[var(--tx2)]">LearnX-AI platform:</span> The LearnX-AI platform, branding, and underlying technology are owned by NordX Labs Oy. You may not copy, reproduce, or create derivative works from the platform.</p>
          </Section>

          <Section num="7" title="Privacy">
            <p>Our collection and use of personal data is described in our <Link href="/privacy" className="text-purple-400 hover:underline">Privacy Policy</Link>, which forms part of these Terms of Service.</p>
          </Section>

          <Section num="8" title="Service Availability">
            <p>We aim to provide a reliable service, but we do not guarantee uninterrupted availability. LearnX-AI is provided "as is" and we reserve the right to modify, suspend, or discontinue the service at any time, with reasonable notice where possible.</p>
            <p>Video generation involves third-party AI services and may occasionally fail due to technical issues outside our control.</p>
          </Section>

          <Section num="9" title="Limitation of Liability">
            <p>To the fullest extent permitted by Finnish law, NordX Labs Oy is not liable for:</p>
            <ul className="list-disc list-inside space-y-1 text-[var(--tx4)]">
              <li>Inaccuracies in AI-generated educational content</li>
              <li>Loss of data due to technical failures</li>
              <li>Indirect or consequential damages arising from use of the service</li>
              <li>Actions taken by users based on AI-generated content without independent verification</li>
            </ul>
          </Section>

          <Section num="10" title="Account Termination">
            <p>You may delete your account at any time via Settings → Delete Account. This will permanently remove your account and all associated data.</p>
            <p>We reserve the right to suspend or terminate accounts that violate these Terms of Service, with notice where practicable.</p>
          </Section>

          <Section num="11" title="Governing Law">
            <p>These Terms of Service are governed by the laws of Finland. Any disputes arising from these terms shall be resolved in the courts of Finland.</p>
          </Section>

          <Section num="12" title="Changes to These Terms">
            <p>We may update these terms from time to time. When we do, we will update the "Last updated" date. Material changes will be communicated via the application or by email. Continued use of LearnX-AI after changes take effect constitutes acceptance of the updated terms.</p>
          </Section>

          <Section num="13" title="Contact">
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
            <Link href="/privacy" className="text-[var(--tx6)] hover:text-[var(--tx1)] text-xs transition-colors">Privacy Policy</Link>
            <Link href="/terms" className="text-purple-400 text-xs">Terms of Service</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
