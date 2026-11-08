"use client";

// Schema mapping: the middle tier (canonical layer), source -> Migration_Staging.mid.<Entity>.
//   Extracted data: the rows of the mid tables.
//   Developer view: each entity's INSERT script; any field's expression can be changed.
import { useRouter } from "next/navigation";
import { useState } from "react";
import { LayerData, LayerScripts, ViewToggle, useView } from "../../components/LayerView";
import { Check, PageHeader, Shell, Toast } from "../../components/ui";
import { ChangeRequests } from "../../components/Workflow";
import { useStore } from "../../lib/store";

export default function CanonicalPage() {
  const router = useRouter();
  const { canonicalApproved, approveCanonical } = useStore();
  const [view, setView] = useView("canonical-view");
  const [toast, setToast] = useState<string | null>(null);
  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(null), 2400); };

  return (
    <Shell>
      <PageHeader title="Canonical layer" actions={<ViewToggle view={view} onChange={setView} dataLabel="Extracted data" />} />

      {view === "developer" ? <LayerScripts layer="middle" initial="candidates" /> : <LayerData layer="middle" initial="candidates" />}

      <div className="flex flex-wrap items-center justify-end gap-2 mt-4">
        {canonicalApproved ? (
          <>
            <span className="mr-auto flex items-center gap-1.5 text-[13px] font-medium text-ok"><Check /> Canonical layer approved</span>
            <button className="btn-primary" onClick={() => router.push("/target")}>Next: Destination data →</button>
          </>
        ) : (
          <button className="btn-primary min-w-[96px]" onClick={() => { approveCanonical(); flash("Canonical layer approved"); }}>Approve</button>
        )}
      </div>

      <div className="mt-5 max-w-[640px]">
        <ChangeRequests onSent={() => flash("Request sent. It will be in the next run.")} />
      </div>
      <Toast message={toast} />
    </Shell>
  );
}
