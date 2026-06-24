"use client";

import { Card } from "@/components/ui";

export default function ComingSoon({ title, desc }) {
  return (
    <Card className="p-10 text-center">
      <div className="mx-auto max-w-md">
        <span className="inline-block rounded-md bg-sand px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
          Coming soon
        </span>
        <h3 className="mt-4 text-lg font-bold text-ink">{title}</h3>
        <p className="mt-2 text-sm text-ink-muted">{desc}</p>
      </div>
    </Card>
  );
}
