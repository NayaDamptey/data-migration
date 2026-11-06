"use client";

// The source tables behind one canonical entity, shown the way a developer would
// write them: the FROM/JOIN part of the entity's SQL. Join type, keys, filters and
// the "keep one row" rule are editable inline, as tokens in the code.
// Real CRMs spread one record across many tables (phones, employment history,
// lookup codes…), so each entity's query can join as many tables as it needs.
import { Fragment, type ReactNode } from "react";
import { SOURCE_COLUMNS, SOURCE_TABLES, suggestJoin, type Entity, type Join } from "../lib/mock";
import { useStore } from "../lib/store";
import { ADDRESS_PART, DEFAULTS } from "../lib/transforms";

// Syntax colours, all in the app's blue range
const C = {
  kw: "text-[#7FA6FF] font-semibold",
  id: "text-[#E6EEFF]",
  str: "text-[#A9C4FF]",
  fn: "text-[#9DB9FF]",
  num: "text-[#C9D8FF]",
  punct: "text-[#8FA3CC]",
  comment: "text-[#5E77A8] italic",
};

export function JoinsPanel({ entity }: { entity: Entity }) {
  const { joins, setJoins, resetJoins, joinsChanged, fieldSource, setFieldSource, transformConfig } = useStore();
  const base = entity.sourceTable;
  if (!base) return null;

  const list = joins(entity.key);
  const inQuery = [base, ...list.map((j) => j.table)];
  const available = Object.keys(SOURCE_COLUMNS).filter((t) => !inQuery.includes(t));
  const baseRows = SOURCE_TABLES.find((t) => t.name === base)?.rows ?? entity.rows;
  const usedBy = (table: string) => entity.fields.filter((f) => fieldSource(entity.key, f.name).from?.startsWith(`${table}.`)).map((f) => f.name);
  const alias = (table: string) => (table === base ? "b" : `j${list.findIndex((j) => j.table === table) + 1}`);

  const update = (id: string, patch: Partial<Join>) =>
    setJoins(entity.key, list.map((j) => (j.id === id ? { ...j, ...patch, matched: -1 } : j))); // keys changed → matches unknown until next run
  const remove = (id: string) => setJoins(entity.key, list.filter((j) => j.id !== id));
  const add = (table: string) => {
    const s = suggestJoin(inQuery, table);
    const join: Join = s
      ? { ...s, id: `j${Date.now()}`, matched: -1 }
      : { id: `j${Date.now()}`, table, type: "left", on: [{ left: `${base}.${SOURCE_COLUMNS[base][0].name}`, right: SOURCE_COLUMNS[table][0].name }], cardinality: "one_to_many", pick: { rule: "latest", orderBy: SOURCE_COLUMNS[table][0].name }, matched: -1 };
    setJoins(entity.key, [...list, join]);
  };

  // Build the editor as a list of lines; each line is inline code with editable tokens
  const lines: ReactNode[] = [];
  const L = (node: ReactNode) => lines.push(node);
  const fieldsOf = (t: string) => { const u = usedBy(t); return u.length ? `feeds ${u.slice(0, 4).join(", ")}${u.length > 4 ? ` +${u.length - 4}` : ""}` : "not used by any field yet"; };

  L(<Cm>-- canonical.{entity.key}: {entity.fields.length} fields from {inQuery.length} source table{inQuery.length > 1 ? "s" : ""}</Cm>);

  // SELECT list: one line per canonical field. The column token is the same mapping as the
  // field table's dropdown, so editing either one updates the other and this SQL.
  const queryCols = inQuery.flatMap((t) => (SOURCE_COLUMNS[t] ?? []).map((c) => ({ value: `${t}.${c.name}`, label: `${alias(t)}."${c.name}"` })));
  L(<K>SELECT</K>);
  entity.fields.forEach((f, i) => {
    const { from, changed } = fieldSource(entity.key, f.name);
    const transform = changed ? undefined : f.transform; // a re-mapped field drops the old column's transform
    const cfg = transformConfig(entity.key, f.name);
    const options = [{ value: "", label: "NULL" }, ...queryCols];
    if (from && !options.some((o) => o.value === from)) options.push({ value: from, label: from });
    const colTok = (
      <Tok id={`sel-${entity.key}-${f.name}`} label={`Source column for ${f.name}`} className={from ? C.id : C.kw} value={from ?? ""}
        options={options} onChange={(v) => setFieldSource(entity.key, f.name, v || null)} />
    );
    const sep = i < entity.fields.length - 1 ? <P>,</P> : null;
    let expr: ReactNode = colTok;
    if (transform === "constant") expr = <S>&apos;{cfg.constant ?? "United Kingdom"}&apos;</S>;
    else if (from && transform === "split_address") expr = <><F>@split_address</F><P>(</P>{colTok}<P>, </P><S>&apos;{ADDRESS_PART[f.name] ?? "line_1"}&apos;</S><P>, </P><S>&apos;{cfg.splitRule ?? DEFAULTS.splitRule}&apos;</S><P>)</P></>;
    else if (from && transform === "parse_date") expr = <><F>@parse_date</F><P>(</P>{colTok}<P>, </P><S>&apos;{cfg.dateFormat ?? DEFAULTS.dateFormat}&apos;</S><P>)</P></>;
    else if (from && transform === "value_map") expr = <><F>@value_map</F><P>(</P>{colTok}<P>, </P><S>&apos;{entity.key}.{f.name}&apos;</S><P>)</P></>;
    else if (from && transform) expr = <><F>@{transform}</F><P>(</P>{colTok}<P>)</P></>;
    L(<><Ind />{expr} <K>AS</K> <Id>{f.name}</Id>{sep}</>);
  });

  L(<><K>FROM</K> <Id>{`"${base}"`}</Id> <K>AS</K> <Id>b</Id><Pad /><Cm>-- {baseRows.toLocaleString()} rows · one per {entity.label.toLowerCase().replace(/s$/, "")} · {fieldsOf(base)}</Cm></>);

  list.forEach((j, i) => {
    const a = `j${i + 1}`;
    const cols = SOURCE_COLUMNS[j.table]?.map((c) => c.name) ?? [];
    const leftCols = inQuery.slice(0, i + 1).flatMap((t) => (SOURCE_COLUMNS[t] ?? []).map((c) => ({ value: `${t}.${c.name}`, label: `${alias(t)}."${c.name}"` })));
    const id = `join-${j.id}`;
    const pct = j.matched >= 0 ? j.matched / baseRows : null;
    const typeTok = (
      <Tok id={`${id}-type`} label="Join type" className={C.kw} value={j.type}
        options={[{ value: "left", label: "LEFT JOIN" }, { value: "inner", label: "INNER JOIN" }]}
        onChange={(v) => update(j.id, { type: v as Join["type"] })} />
    );
    const onLine = (
      <>
        {j.on.map((k, ki) => (
          <Fragment key={ki}>
            {ki > 0 && <> <K>AND</K> </>}
            <Id>{a}.</Id><Tok id={`${id}-r${ki}`} label={`Key in ${j.table}`} className={C.id} value={k.right}
              options={cols.map((c) => ({ value: c, label: `"${c}"` }))}
              onChange={(v) => update(j.id, { on: j.on.map((x, xi) => (xi === ki ? { ...x, right: v } : x)) })} />
            <P> = </P>
            <Tok id={`${id}-l${ki}`} label="Key in query" className={C.id} value={k.left} options={leftCols}
              onChange={(v) => update(j.id, { on: j.on.map((x, xi) => (xi === ki ? { ...x, left: v } : x)) })} />
          </Fragment>
        ))}
      </>
    );
    // The filter condition. In a "keep one" subquery it's the subquery's WHERE; on a plain
    // LEFT JOIN it must go in the ON clause (a WHERE after the join would drop unmatched rows).
    const condition = j.filter ? (
      <>
        {prefixFor(j)} <Tok id={`${id}-fc`} label="Filter column" className={C.id} value={j.filter.column}
          options={cols.map((c) => ({ value: c, label: j.cardinality === "one_to_many" ? `"${c}"` : `${a}."${c}"` }))} onChange={(v) => update(j.id, { filter: { ...j.filter!, column: v } })} />
        <P> = </P><S>&apos;</S>
        <label className="sr-only" htmlFor={`${id}-fv`}>Filter value</label>
        <input id={`${id}-fv`} value={j.filter.value} style={{ width: `${Math.max(1, j.filter.value.length)}ch` }}
          onChange={(e) => update(j.id, { filter: { ...j.filter!, value: e.target.value } })}
          className={`${C.str} bg-transparent border-b border-dotted border-current outline-none focus:bg-nav-hover px-0`} />
        <S>&apos;</S>
        <Act onClick={() => update(j.id, { filter: undefined })} label="Remove filter">× {j.cardinality === "one_to_many" ? "WHERE" : "AND"}</Act>
      </>
    ) : null;
    const addFilter = !j.filter && (
      <Act onClick={() => update(j.id, { filter: { column: cols[1] ?? cols[0], value: "" } })} label="Add a row filter">
        + {j.cardinality === "one_to_many" ? "WHERE" : "AND"}
      </Act>
    );

    L(<span />);
    if (j.cardinality === "one_to_many" && j.pick) {
      const part = j.on.map((k) => `"${k.right}"`).join(", ");
      L(<>{typeTok} <P>(</P></>);
      L(<><Ind /><K>SELECT</K> <P>*,</P> <F>ROW_NUMBER</F><P>()</P> <K>OVER</K> <P>(</P><K>PARTITION BY</K> <Id>{part}</Id> <K>ORDER BY</K>{" "}
        <Tok id={`${id}-order`} label="Order by" className={C.id} value={j.pick.orderBy} options={cols.map((c) => ({ value: c, label: `"${c}"` }))}
          onChange={(v) => update(j.id, { pick: { ...j.pick!, orderBy: v } })} />{" "}
        <Tok id={`${id}-rule`} label="Keep latest or earliest" className={C.kw} value={j.pick.rule}
          options={[{ value: "latest", label: "DESC" }, { value: "earliest", label: "ASC" }]}
          onChange={(v) => update(j.id, { pick: { ...j.pick!, rule: v as "latest" | "earliest" } })} />
        <P>)</P> <K>AS</K> <Id>rn</Id></>);
      L(<><Ind /><K>FROM</K> <Id>{`"${j.table}"`}</Id>{addFilter}</>);
      if (condition) L(<><Ind />{condition}</>);
      L(<><P>)</P> <K>AS</K> <Id>{a}</Id> <K>ON</K> {onLine} <K>AND</K> <Id>{a}.rn</Id> <P>=</P> <N>1</N></>);
    } else {
      L(<>{typeTok} <Id>{`"${j.table}"`}</Id> <K>AS</K> <Id>{a}</Id></>);
      L(<><Ind /><K>ON</K> {onLine}{addFilter}</>);
      if (condition) L(<><Ind />{"   "}{condition}</>);
    }
    L(
      <>
        <Cm>-- </Cm>
        <Tok id={`${id}-card`} label="Rows per record" className={C.comment} value={j.cardinality}
          options={[{ value: "many_to_one", label: "one match per record" }, { value: "one_to_many", label: "several matches: keep one" }]}
          onChange={(v) => update(j.id, v === "many_to_one" ? { cardinality: "many_to_one", pick: undefined } : { cardinality: "one_to_many", pick: j.pick ?? { rule: "latest", orderBy: cols[cols.length - 1] } })} />
        <Cm>
          {" · "}
          {pct === null ? "changed, match count updates on the next run" : `${j.matched.toLocaleString()} of ${baseRows.toLocaleString()} matched (${Math.round(pct * 100)}%)`}
          {j.type === "inner" && pct !== null && pct < 1 ? ` · INNER JOIN drops ${(baseRows - j.matched).toLocaleString()}` : ""}
          {" · "}{fieldsOf(j.table)}
        </Cm>
        <Act onClick={() => remove(j.id)} label={`Remove join to ${j.table}`}>× JOIN</Act>
      </>,
    );
  });

  L(<span />);
  L(
    <>
      <Cm>-- </Cm>
      <label className="sr-only" htmlFor={`add-join-${entity.key}`}>Join another table</label>
      <select id={`add-join-${entity.key}`} value="" onChange={(e) => e.target.value && add(e.target.value)}
        className={`${C.kw} bg-transparent appearance-none cursor-pointer border-b border-dotted border-current hover:bg-nav-hover`}>
        <option value="" className="bg-white text-ink">+ JOIN another table…</option>
        {available.map((t) => <option key={t} value={t} className="bg-white text-ink">{t}{suggestJoin(inQuery, t) ? "  (key match found)" : ""}</option>)}
      </select>
    </>,
  );

  return (
    <div className="border-b border-line">
      <div className="flex flex-wrap items-center justify-between gap-2 px-5 pt-4 pb-3">
        <div>
          <h3 className="text-[13px] font-semibold">SQL model <span className="text-muted font-normal">· {inQuery.length} source table{inQuery.length > 1 ? "s" : ""}</span></h3>
          <p className="text-[12px] text-muted">Dotted parts of the code are editable. Changes here and in the field table below stay in sync.</p>
        </div>
        <div className="flex gap-1">
          {joinsChanged(entity.key) && <button className="btn-ghost h-7 px-2.5 text-[12px]" onClick={() => resetJoins(entity.key)}>Reset joins</button>}
        </div>
      </div>

      <div className="mx-5 mb-4 bg-nav font-mono text-[12.5px] leading-[1.9]">
        <div className="flex items-center gap-2 px-4 h-9 border-b border-nav-line text-[11.5px] text-nav-text">
          <span className="text-white">{entity.key}.sql</span>
          <span className="text-[#5E77A8]">· generated T-SQL</span>
        </div>
        <div className="overflow-x-auto py-3">
          <table className="border-collapse">
            <tbody>
              {lines.map((line, n) => (
                <tr key={n} className="hover:bg-nav-hover/60">
                  <td className="select-none text-right pl-4 pr-4 text-[#3E5687] tabular-nums align-top w-10">{n + 1}</td>
                  <td className="pr-6 whitespace-pre text-[#E6EEFF]">{line}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ---- code tokens ----

const K = ({ children }: { children: ReactNode }) => <span className={C.kw}>{children}</span>;
const Id = ({ children }: { children: ReactNode }) => <span className={C.id}>{children}</span>;
const S = ({ children }: { children: ReactNode }) => <span className={C.str}>{children}</span>;
const F = ({ children }: { children: ReactNode }) => <span className={C.fn}>{children}</span>;
const N = ({ children }: { children: ReactNode }) => <span className={C.num}>{children}</span>;
const P = ({ children }: { children: ReactNode }) => <span className={C.punct}>{children}</span>;
const Cm = ({ children }: { children: ReactNode }) => <span className={C.comment}>{children}</span>;
const Ind = () => <span>{"    "}</span>;
const Pad = () => <span>{"   "}</span>;

const prefixFor = (j: Join) => <K>{j.cardinality === "one_to_many" ? "WHERE" : "AND"}</K>;

/** An editable token: a native select styled to sit inside a line of code. */
function Tok({ id, label, value, options, onChange, className }: {
  id: string; label: string; value: string; options: { value: string; label: string }[]; onChange: (v: string) => void; className: string;
}) {
  // Monospace, so the token can be exactly as wide as its current text (no gap after it)
  const text = options.find((o) => o.value === value)?.label ?? value;
  return (
    <>
      <label className="sr-only" htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} title={label} style={{ width: `${text.length}ch` }}
        className={`${className} bg-transparent appearance-none cursor-pointer border-b border-dotted border-current hover:bg-nav-hover focus:bg-nav-hover outline-none px-0`}>
        {options.map((o) => <option key={o.value} value={o.value} className="bg-white text-ink not-italic font-normal">{o.label}</option>)}
      </select>
    </>
  );
}

function Act({ onClick, label, children }: { onClick: () => void; label: string; children: ReactNode }) {
  return (
    <button onClick={onClick} aria-label={label} title={label}
      className="ml-4 px-1.5 text-[11px] text-[#5E77A8] hover:text-white hover:bg-nav-hover not-italic">
      {children}
    </button>
  );
}
