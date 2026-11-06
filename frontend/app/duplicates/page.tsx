// Duplicates now live in a tab of the Data quality page; keep old links working.
import { redirect } from "next/navigation";

export default async function DuplicatesRedirect({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const p = await searchParams;
  const q = new URLSearchParams({ tab: "duplicates", ...(p.entity ? { entity: p.entity } : {}), ...(p.source ? { source: p.source } : {}) });
  redirect(`/quality?${q.toString()}`);
}
