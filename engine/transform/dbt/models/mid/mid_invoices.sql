-- generated: the middle tier for Invoices, with the reviewer's duplicate merges applied
{{ config(alias='Invoices') }}
SELECT
    s.invoice_id,
    s.invoice_no,
    s.po_no,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'client' AND m.duplicate = s.client_id), s.client_id) AS client_id,
    s.invoice_type,
    s.status,
    s.currency,
    s.net_amount,
    s.vat_amount,
    s.gross_amount,
    s.invoice_date,
    s.due_date,
    s.description,
    s.added_by
FROM {{ ref('stg_invoices') }} s
