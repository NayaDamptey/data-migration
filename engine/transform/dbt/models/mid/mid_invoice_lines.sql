{{ config(alias='InvoiceLines') }}
SELECT
    s.line_id,
    s.invoice_id,
    s.placement_id,
    s.description,
    s.quantity,
    s.unit_price,
    s.amount,
    s.created_at
FROM {{ ref('stg_invoice_lines') }} s
