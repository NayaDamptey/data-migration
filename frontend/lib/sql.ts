// The SQL text of one canonical entity's model, and a line diff between two versions.
// Used by Version review to show what a set of mapping changes does to the SQL.
import type { Entity, Join } from "./mock";
import { ADDRESS_PART, DEFAULTS, type TransformConfig } from "./transforms";

export type ResolvedField = { from: string | null; transform?: string; cfg: TransformConfig };

const ident = (s: string) => `"${s.replace(/"/g, '""')}"`;
const literal = (s: string) => `'${s.replace(/'/g, "''")}'`;

export function entitySql(entity: Entity, joins: Join[], resolve: (field: string) => ResolvedField): string {
  const base = entity.sourceTable;
  if (!base) return `-- canonical.${entity.key}: no source table`;
  const alias = new Map<string, string>([[base, "b"]]);
  joins.forEach((j, i) => alias.set(j.table, `j${i + 1}`));
  const col = (q: string) => { const [t, c] = q.split("."); return `${alias.get(t) ?? ident(t)}.${ident(c)}`; };

  const select = entity.fields.map((f, i) => {
    const { from, transform, cfg } = resolve(f.name);
    const src = from && alias.has(from.split(".")[0]) ? col(from) : null;
    let expr = src ?? "NULL";
    if (transform === "constant") expr = literal(cfg.constant ?? "United Kingdom");
    else if (src && transform === "split_address") expr = `@split_address(${src}, ${literal(ADDRESS_PART[f.name] ?? "line_1")}, ${literal(cfg.splitRule ?? DEFAULTS.splitRule)})`;
    else if (src && transform === "parse_date") expr = `@parse_date(${src}, ${literal(cfg.dateFormat ?? DEFAULTS.dateFormat)})`;
    else if (src && transform === "value_map") expr = `@value_map(${src}, ${literal(`${entity.key}.${f.name}`)})`;
    else if (src && transform) expr = `@${transform}(${src})`;
    return `    ${expr} AS ${f.name}${i < entity.fields.length - 1 ? "," : ""}`;
  });

  const lines = ["SELECT", ...select, `FROM ${ident(base)} AS b`];
  joins.forEach((j, i) => {
    const a = `j${i + 1}`;
    const on = j.on.map((k) => `${a}.${ident(k.right)} = ${col(k.left)}`);
    const type = `${j.type.toUpperCase()} JOIN`;
    if (j.cardinality === "one_to_many" && j.pick) {
      const part = j.on.map((k) => ident(k.right)).join(", ");
      lines.push(`${type} (`);
      lines.push(`    SELECT *, ROW_NUMBER() OVER (PARTITION BY ${part} ORDER BY ${ident(j.pick.orderBy)} ${j.pick.rule === "latest" ? "DESC" : "ASC"}) AS rn`);
      lines.push(`    FROM ${ident(j.table)}`);
      if (j.filter) lines.push(`    WHERE ${ident(j.filter.column)} = ${literal(j.filter.value)}`);
      lines.push(`) AS ${a} ON ${on.join(" AND ")} AND ${a}.rn = 1`);
    } else {
      lines.push(`${type} ${ident(j.table)} AS ${a}`);
      lines.push(`    ON ${on.join(" AND ")}`);
      // Filter in ON: a WHERE after a LEFT JOIN would drop the unmatched base rows
      if (j.filter) lines.push(`    AND ${a}.${ident(j.filter.column)} = ${literal(j.filter.value)}`);
    }
  });
  return lines.join("\n");
}

export type DiffLine = { kind: "same" | "add" | "del"; text: string; oldNo?: number; newNo?: number };

/** Line diff (longest common subsequence), good enough for model-sized SQL. */
export function diffLines(before: string, after: string): DiffLine[] {
  const a = before.split("\n");
  const b = after.split("\n");
  const n = a.length, m = b.length;
  const lcs: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
  const out: DiffLine[] = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { out.push({ kind: "same", text: a[i], oldNo: i + 1, newNo: j + 1 }); i++; j++; }
    else if (lcs[i + 1][j] >= lcs[i][j + 1]) { out.push({ kind: "del", text: a[i], oldNo: i + 1 }); i++; }
    else { out.push({ kind: "add", text: b[j], newNo: j + 1 }); j++; }
  }
  while (i < n) { out.push({ kind: "del", text: a[i], oldNo: i + 1 }); i++; }
  while (j < m) { out.push({ kind: "add", text: b[j], newNo: j + 1 }); j++; }
  return out;
}
