// Version review: what changed in the mapping since the last saved version.
// The mapping state is the AI's original spec (lib/mock.ts) plus the reviewer's
// overrides. A saved version is a snapshot of those overrides; the pending
// changes are the difference between that snapshot and the current overrides.
import { ENTITIES, ENTITY_JOINS, type FieldStatus, type Join } from "./mock";
import type { ResolvedField } from "./sql";
import type { TransformConfig } from "./transforms";

export type Overrides = {
  status: Record<string, FieldStatus>;
  source: Record<string, string | null>;
  configs: Record<string, TransformConfig>;
  joins: Record<string, Join[]>;
};

export const EMPTY_OVERRIDES: Overrides = { status: {}, source: {}, configs: {}, joins: {} };

export type ChangeKind = "Mapping" | "Transform" | "Join" | "Review";

export type Change = {
  id: string;
  entity: string;
  kind: ChangeKind;
  subject: string;
  before: string;
  after: string;
  revert: (current: Overrides) => Overrides;
};

const original = (entity: string, field: string) => ENTITIES.find((e) => e.key === entity)?.fields.find((x) => x.name === field);

/** Split rules are shared by every field fed from the same address column; other settings are per field. */
export function configKey(entity: string, field: string) {
  const f = original(entity, field);
  return f?.transform === "split_address" ? `${f.from}|split_address` : `${entity}.${field}`;
}

export const sourceOf = (o: Overrides, entity: string, field: string) => {
  const key = `${entity}.${field}`;
  return key in o.source ? o.source[key] : original(entity, field)?.from ?? null;
};
export const statusOf = (o: Overrides, entity: string, field: string): FieldStatus =>
  o.status[`${entity}.${field}`] ?? original(entity, field)?.status ?? "unmapped";
export const configOf = (o: Overrides, entity: string, field: string): TransformConfig => o.configs[configKey(entity, field)] ?? {};
export const joinsOf = (o: Overrides, entity: string): Join[] => o.joins[entity] ?? ENTITY_JOINS[entity] ?? [];

/** What the SQL builder needs for one field in a given state. A re-mapped field drops the old column's transform. */
export function resolveIn(o: Overrides, entity: string, field: string): ResolvedField {
  const from = sourceOf(o, entity, field);
  const f = original(entity, field);
  return { from, transform: from === (f?.from ?? null) ? f?.transform : undefined, cfg: configOf(o, entity, field) };
}

// Copy one key's value (or its absence) from one map to another
function copyKey<T>(into: Record<string, T>, from: Record<string, T>, key: string): Record<string, T> {
  const out = { ...into };
  if (key in from) out[key] = from[key];
  else delete out[key];
  return out;
}

const STATUS_LABEL: Record<FieldStatus, string> = { mapped: "Mapped", review: "Needs review", unmapped: "Unmapped" };
const SPLIT_LABEL: Record<string, string> = { last_comma: "city after the last comma", first_comma: "everything after the first comma", none: "don’t split" };
const DATE_LABEL: Record<string, string> = { DMY: "Day/Month/Year", MDY: "Month/Day/Year" };

function describeConfigChange(before: TransformConfig, after: TransformConfig): [string, string] {
  const b: string[] = [], a: string[] = [];
  if ((before.splitRule ?? "last_comma") !== (after.splitRule ?? "last_comma")) {
    b.push(`split: ${SPLIT_LABEL[before.splitRule ?? "last_comma"]}`);
    a.push(`split: ${SPLIT_LABEL[after.splitRule ?? "last_comma"]}`);
  }
  if ((before.dateFormat ?? "DMY") !== (after.dateFormat ?? "DMY")) {
    b.push(`dates: ${DATE_LABEL[before.dateFormat ?? "DMY"]}`);
    a.push(`dates: ${DATE_LABEL[after.dateFormat ?? "DMY"]}`);
  }
  if ((before.constant ?? "United Kingdom") !== (after.constant ?? "United Kingdom")) {
    b.push(`“${before.constant ?? "United Kingdom"}”`);
    a.push(`“${after.constant ?? "United Kingdom"}”`);
  }
  if (before.valueMap || after.valueMap) {
    const bm = before.valueMap ?? {}, am = after.valueMap ?? {};
    for (const k of Array.from(new Set([...Object.keys(bm), ...Object.keys(am)]))) {
      if (bm[k] === am[k]) continue;
      const show = (v: string | undefined) => (v === undefined ? "not mapped" : v === "" ? "blank" : v);
      b.push(`“${k}” → ${show(bm[k])}`);
      a.push(`“${k}” → ${show(am[k])}`);
    }
  }
  return [b.join("; ") || "default settings", a.join("; ") || "default settings"];
}

export function describeJoin(j: Join): string {
  const on = j.on.map((k) => `${j.table}.${k.right} = ${k.left}`).join(" AND ");
  const filter = j.filter ? ` · only ${j.filter.column} = '${j.filter.value}'` : "";
  const pick = j.cardinality === "one_to_many" && j.pick ? ` · keep ${j.pick.rule} by ${j.pick.orderBy}` : "";
  return `${j.type.toUpperCase()} JOIN ${j.table} ON ${on}${filter}${pick}`;
}

// Join definitions compared without the run statistics
const joinShape = (j: Join) => JSON.stringify({ ...j, matched: undefined });

export function computeChanges(base: Overrides, cur: Overrides): Change[] {
  const changes: Change[] = [];
  for (const e of ENTITIES) {
    // Field mappings and review decisions
    for (const f of e.fields) {
      const key = `${e.key}.${f.name}`;
      const sb = sourceOf(base, e.key, f.name), sc = sourceOf(cur, e.key, f.name);
      if (sb !== sc) {
        changes.push({
          id: `map:${key}`, entity: e.key, kind: "Mapping", subject: f.name,
          before: sb ?? "not mapped", after: sc ?? "not mapped",
          revert: (o) => ({ ...o, source: copyKey(o.source, base.source, key), status: copyKey(o.status, base.status, key) }),
        });
        continue;
      }
      const stb = statusOf(base, e.key, f.name), stc = statusOf(cur, e.key, f.name);
      if (stb !== stc) {
        changes.push({
          id: `review:${key}`, entity: e.key, kind: "Review", subject: f.name,
          before: STATUS_LABEL[stb], after: STATUS_LABEL[stc],
          revert: (o) => ({ ...o, status: copyKey(o.status, base.status, key) }),
        });
      }
    }

    // Transform settings (one entry per setting group; a split rule covers several fields)
    const seen = new Set<string>();
    for (const f of e.fields) {
      if (!f.transform) continue;
      const ck = configKey(e.key, f.name);
      if (seen.has(ck)) continue;
      seen.add(ck);
      const cb = base.configs[ck] ?? {}, cc = cur.configs[ck] ?? {};
      if (JSON.stringify(cb) === JSON.stringify(cc)) continue;
      const fields = e.fields.filter((x) => configKey(e.key, x.name) === ck).map((x) => x.name);
      const [before, after] = describeConfigChange(cb, cc);
      changes.push({
        id: `transform:${ck}`, entity: e.key, kind: "Transform", subject: `${fields.join(", ")} · ${f.transform.replace(/_/g, " ")}`,
        before, after,
        revert: (o) => ({ ...o, configs: copyKey(o.configs, base.configs, ck) }),
      });
    }

    // Joins: added, removed or edited
    const jb = joinsOf(base, e.key), jc = joinsOf(cur, e.key);
    const setJoins = (o: Overrides, list: Join[]) => ({ ...o, joins: { ...o.joins, [e.key]: list } });
    for (const j of jc) {
      const old = jb.find((x) => x.id === j.id);
      if (!old) {
        changes.push({
          id: `join+:${e.key}:${j.id}`, entity: e.key, kind: "Join", subject: `added ${j.table}`,
          before: "—", after: describeJoin(j),
          revert: (o) => setJoins(o, joinsOf(o, e.key).filter((x) => x.id !== j.id)),
        });
      } else if (joinShape(old) !== joinShape(j)) {
        changes.push({
          id: `join~:${e.key}:${j.id}`, entity: e.key, kind: "Join", subject: `changed ${j.table}`,
          before: describeJoin(old), after: describeJoin(j),
          revert: (o) => setJoins(o, joinsOf(o, e.key).map((x) => (x.id === j.id ? old : x))),
        });
      }
    }
    jb.forEach((old, index) => {
      if (jc.some((x) => x.id === old.id)) return;
      changes.push({
        id: `join-:${e.key}:${old.id}`, entity: e.key, kind: "Join", subject: `removed ${old.table}`,
        before: describeJoin(old), after: "—",
        revert: (o) => { const list = [...joinsOf(o, e.key)]; list.splice(Math.min(index, list.length), 0, old); return setJoins(o, list); },
      });
    });
  }
  return changes;
}
