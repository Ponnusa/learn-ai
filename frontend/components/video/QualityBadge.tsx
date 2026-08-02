const TIER_CONFIG: Record<string, { label: string; cls: string; desc: string }> = {
  premium:  {
    label: 'Premium quality',
    cls:   'bg-purple-500/15 text-purple-400 border-purple-500/20',
    desc:  'Our best AI — richer animations, more scenes, longer duration',
  },
  enhanced: {
    label: 'Enhanced quality',
    cls:   'bg-blue-500/15 text-blue-400 border-blue-500/20',
    desc:  'High-quality animation tuned for your topic',
  },
  standard: {
    label: 'Standard quality',
    cls:   'bg-[var(--ov3)] text-[var(--tx5)] border-[var(--bd)]',
    desc:  'Sign in to unlock Enhanced quality for free',
  },
};

export function QualityBadge({ tier }: { tier: string }) {
  const cfg = TIER_CONFIG[tier] ?? TIER_CONFIG.premium;
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium whitespace-nowrap ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}

export function QualityBanner({ tier }: { tier: string }) {
  const cfg = TIER_CONFIG[tier] ?? TIER_CONFIG.premium;
  return (
    <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl
                    border border-purple-500/15 bg-purple-500/5">
      <QualityBadge tier={tier} />
      <span className="text-[var(--tx6)] text-xs">{cfg.desc}</span>
    </div>
  );
}
