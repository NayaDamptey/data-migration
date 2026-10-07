"use client";

// Prototype state shared across screens. Lives in memory for the session;
// swap for TanStack Query + the FastAPI routes when the backend is ready.
import { createContext, useCallback, useContext, useMemo, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { ENTITIES, ENTITY_JOINS, INITIAL_REQUESTS, INITIAL_RUNS, INITIAL_UPLOADS, type FieldStatus, type Join, type Run } from "./mock";
import type { TransformConfig } from "./transforms";
import type { UploadItem } from "./upload";
import { EMPTY_OVERRIDES, computeChanges, type Change, type Overrides } from "./versions";

export type StepState = "idle" | "running" | "done";

export type Setup = {
  sourceSystem: string;
  sourceFormat: string;
  targetSystem: string;
  targetDatabase: string;
  output: string;
};

type ChangeRequest = { id: string; text: string; status: "open" | "done"; when: string };

type Store = {
  projectId: string;
  setup: Setup;
  updateSetup: (patch: Partial<Setup>) => void;
  uploads: UploadItem[];
  setUploads: Dispatch<SetStateAction<UploadItem[]>>;
  steps: { inspect: StepState; canonical: StepState; target: StepState };
  runStep: (step: "inspect" | "canonical" | "target") => Promise<void>;
  runs: Run[];
  requests: ChangeRequest[];
  addRequest: (text: string) => void;
  setFieldStatus: (entity: string, field: string, status: FieldStatus) => void;
  fieldStatus: (entity: string, field: string) => FieldStatus;
  /** Source column a canonical field is mapped from, after any change by the reviewer. */
  fieldSource: (entity: string, field: string) => { from: string | null; changed: boolean };
  setFieldSource: (entity: string, field: string, from: string | null) => void;
  resetField: (entity: string, field: string) => void;
  /** Transform settings (split rule, date format, value map…) chosen by the reviewer. */
  transformConfig: (entity: string, field: string) => TransformConfig;
  setTransformConfig: (entity: string, field: string, patch: TransformConfig) => void;
  /** True if the reviewer changed this field's source column or transform settings. */
  isChanged: (entity: string, field: string) => boolean;
  joins: (entity: string) => Join[];
  setJoins: (entity: string, joins: Join[]) => void;
  resetJoins: (entity: string) => void;
  joinsChanged: (entity: string) => boolean;
  changedFields: number;
  /** The reviewer approved the canonical model. Any mapping change after that needs approving again. */
  canonicalApproved: boolean;
  approveCanonical: () => void;
  /** Version review: changes since the last saved version, and the two states being compared. */
  pendingChanges: Change[];
  savedOverrides: Overrides;
  currentOverrides: Overrides;
  revertChange: (id: string) => void;
  discardChanges: () => void;
  saveVersion: (label: string) => number;
};

// Split rules are shared by every field fed from the same address column
// (address_line_1 and city both come from one split); other settings are per field.
const configKey = (entity: string, field: string) => {
  const f = original(entity, field);
  return f?.transform === "split_address" ? `${f.from}|split_address` : `${entity}.${field}`;
};

const Ctx = createContext<Store | null>(null);

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
const original = (entity: string, field: string) => ENTITIES.find((e) => e.key === entity)?.fields.find((x) => x.name === field);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [setup, setSetup] = useState<Setup>({
    sourceSystem: "Tracker",
    sourceFormat: "CSV files",
    targetSystem: "Bullhorn",
    targetDatabase: "PostgreSQL",
    output: "CSV files",
  });
  const [uploads, setUploads] = useState<UploadItem[]>(INITIAL_UPLOADS);
  const [steps, setSteps] = useState<Store["steps"]>({ inspect: "done", canonical: "done", target: "idle" });
  const [runs, setRuns] = useState<Run[]>(INITIAL_RUNS);
  const [requests, setRequests] = useState<ChangeRequest[]>(INITIAL_REQUESTS);
  const [statusOverrides, setStatusOverrides] = useState<Record<string, FieldStatus>>({});
  const [sourceOverrides, setSourceOverrides] = useState<Record<string, string | null>>({});
  const [configs, setConfigs] = useState<Record<string, TransformConfig>>({});
  const [joinOverrides, setJoinOverrides] = useState<Record<string, Join[]>>({});
  // Snapshot of the mapping state at approval; approval holds only while nothing has changed since
  const [approvedSnapshot, setApprovedSnapshot] = useState<string | null>(null);
  // The overrides as of the last saved version (v3 = the AI spec with no overrides)
  const [savedOverrides, setSavedOverrides] = useState<Overrides>(EMPTY_OVERRIDES);

  const runStep = useCallback(async (step: "inspect" | "canonical" | "target") => {
    setSteps((s) => ({ ...s, [step]: "running" }));
    if (step === "canonical") {
      setRuns((r) => [
        { id: `r-${r.length + 1}`, version: r.length + 1, label: "Canonical layer re-run", when: "Just now", by: "You", status: "running" },
        ...r,
      ]);
    }
    await wait(step === "inspect" ? 1400 : 2000);
    setSteps((s) => ({ ...s, [step]: "done" }));
    setRuns((r) => r.map((x) => (x.status === "running" ? { ...x, status: "complete" } : x)));
  }, []);

  const addRequest = useCallback((text: string) => {
    setRequests((r) => [{ id: `cr-${Date.now()}`, text, status: "open", when: "Just now" }, ...r]);
  }, []);

  const setFieldStatus = useCallback((entity: string, field: string, status: FieldStatus) => {
    setStatusOverrides((o) => ({ ...o, [`${entity}.${field}`]: status }));
  }, []);

  const fieldStatus = useCallback(
    (entity: string, field: string): FieldStatus => statusOverrides[`${entity}.${field}`] ?? original(entity, field)?.status ?? "unmapped",
    [statusOverrides],
  );

  const fieldSource = useCallback(
    (entity: string, field: string) => {
      const key = `${entity}.${field}`;
      const orig = original(entity, field)?.from ?? null;
      if (!(key in sourceOverrides)) return { from: orig, changed: false };
      return { from: sourceOverrides[key], changed: sourceOverrides[key] !== orig };
    },
    [sourceOverrides],
  );

  const setFieldSource = useCallback((entity: string, field: string, from: string | null) => {
    const key = `${entity}.${field}`;
    setSourceOverrides((o) => ({ ...o, [key]: from }));
    // A person chose this column, so it no longer needs review
    setStatusOverrides((o) => ({ ...o, [key]: from ? "mapped" : "unmapped" }));
  }, []);

  const resetField = useCallback((entity: string, field: string) => {
    const without = (key: string) => <T,>(o: Record<string, T>) => { const { [key]: _, ...rest } = o; return rest; };
    setSourceOverrides(without(`${entity}.${field}`));
    setStatusOverrides(without(`${entity}.${field}`));
    setConfigs(without(configKey(entity, field)));
  }, []);

  const transformConfig = useCallback((entity: string, field: string) => configs[configKey(entity, field)] ?? {}, [configs]);
  const setTransformConfig = useCallback((entity: string, field: string, patch: TransformConfig) => {
    const key = configKey(entity, field);
    setConfigs((c) => ({ ...c, [key]: { ...c[key], ...patch } }));
  }, []);

  const isChanged = useCallback(
    (entity: string, field: string) => fieldSource(entity, field).changed || configKey(entity, field) in configs,
    [fieldSource, configs],
  );

  const joins = useCallback((entity: string) => joinOverrides[entity] ?? ENTITY_JOINS[entity] ?? [], [joinOverrides]);
  const setJoins = useCallback((entity: string, j: Join[]) => setJoinOverrides((o) => ({ ...o, [entity]: j })), []);
  const resetJoins = useCallback((entity: string) => setJoinOverrides(({ [entity]: _, ...rest }) => rest), []);
  const joinsChanged = useCallback(
    (entity: string) => entity in joinOverrides && JSON.stringify(joinOverrides[entity]) !== JSON.stringify(ENTITY_JOINS[entity] ?? []),
    [joinOverrides],
  );

  const changedFields =
    Object.keys(sourceOverrides).filter((k) => {
      const [entity, field] = k.split(".");
      return sourceOverrides[k] !== (original(entity, field)?.from ?? null);
    }).length +
    Object.keys(configs).length +
    Object.keys(joinOverrides).filter((e) => joinsChanged(e)).length;

  const mappingSnapshot = JSON.stringify([statusOverrides, sourceOverrides, configs, joinOverrides]);
  const canonicalApproved = approvedSnapshot === mappingSnapshot;
  const approveCanonical = useCallback(() => setApprovedSnapshot(mappingSnapshot), [mappingSnapshot]);

  // ---- Version review ----
  const currentOverrides = useMemo<Overrides>(
    () => ({ status: statusOverrides, source: sourceOverrides, configs, joins: joinOverrides }),
    [statusOverrides, sourceOverrides, configs, joinOverrides],
  );
  const pendingChanges = useMemo(() => computeChanges(savedOverrides, currentOverrides), [savedOverrides, currentOverrides]);
  const applyOverrides = useCallback((o: Overrides) => {
    setStatusOverrides(o.status);
    setSourceOverrides(o.source);
    setConfigs(o.configs);
    setJoinOverrides(o.joins);
  }, []);
  const revertChange = useCallback((id: string) => {
    const c = pendingChanges.find((x) => x.id === id);
    if (c) applyOverrides(c.revert(currentOverrides));
  }, [pendingChanges, currentOverrides, applyOverrides]);
  const discardChanges = useCallback(() => applyOverrides(savedOverrides), [applyOverrides, savedOverrides]);
  const saveVersion = useCallback((label: string) => {
    const version = Math.max(0, ...runs.map((r) => r.version)) + 1;
    setRuns((r) => [{ id: `r-${version}`, version, label: label.trim() || "Mapping changes", when: "Just now", by: "Naya Damptey", status: "complete" }, ...r]);
    setSavedOverrides(currentOverrides);
    return version;
  }, [runs, currentOverrides]);

  const value = useMemo<Store>(
    () => ({
      projectId: "spencer-thomas-tracker-bullhorn",
      setup,
      updateSetup: (patch) => setSetup((s) => ({ ...s, ...patch })),
      uploads,
      setUploads,
      steps,
      runStep,
      runs,
      requests,
      addRequest,
      setFieldStatus,
      fieldStatus,
      fieldSource,
      setFieldSource,
      resetField,
      transformConfig,
      setTransformConfig,
      isChanged,
      joins,
      setJoins,
      resetJoins,
      joinsChanged,
      changedFields,
      canonicalApproved,
      approveCanonical,
      pendingChanges,
      savedOverrides,
      currentOverrides,
      revertChange,
      discardChanges,
      saveVersion,
    }),
    [setup, uploads, steps, runStep, runs, requests, addRequest, setFieldStatus, fieldStatus, fieldSource, setFieldSource, resetField,
      transformConfig, setTransformConfig, isChanged, joins, setJoins, resetJoins, joinsChanged, changedFields, canonicalApproved, approveCanonical,
      pendingChanges, savedOverrides, currentOverrides, revertChange, discardChanges, saveVersion],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore() {
  const s = useContext(Ctx);
  if (!s) throw new Error("useStore must be used inside StoreProvider");
  return s;
}
