-- generated from spec/target.yml: middle tier -> Invoice
{{ config(alias='Invoice') }}
SELECT
    TRY_CAST(TRY_CAST(inv.invoice_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(inv.invoice_type AS VARCHAR) AS Type,
    TRY_CAST(inv.invoice_no AS VARCHAR) AS InvoiceNo,
    TRY_CAST((SELECT TRY_CAST(l.placement_id AS INT) FROM {{ ref('mid_invoice_lines') }} AS l WHERE l.invoice_id = inv.invoice_id AND NOT l.placement_id IS NULL LIMIT 1) AS INTEGER) AS PlacementID,
    TRY_CAST(inv.net_amount AS DECIMAL(8,2)) AS Amount,
    TRY_CAST(inv.vat_amount AS DECIMAL(8,2)) AS TaxAmount,
    TRY_CAST(inv.currency AS VARCHAR) AS Currency,
    TRY_CAST(inv.invoice_date AS DATE) AS InvoiceDate,
    TRY_CAST(inv.due_date AS DATE) AS DueDate,
    TRY_CAST(UPPER(LEFT(CAST(inv.status AS TEXT), 1)) || SUBSTRING(inv.status, 2, 50) AS VARCHAR) AS Status,
    TRY_CAST(inv.description AS VARCHAR) AS Notes,
    TRY_CAST(inv.added_by AS VARCHAR) AS AddedBy
FROM {{ ref('mid_invoices') }} AS inv
