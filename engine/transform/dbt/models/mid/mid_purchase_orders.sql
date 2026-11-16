-- generated: the middle tier for Purchase orders, with the reviewer's duplicate merges applied
{{ config(alias='PurchaseOrders') }}
SELECT
    s.po_no,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'client' AND m.duplicate = s.client_id), s.client_id) AS client_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'job' AND m.duplicate = s.job_id), s.job_id) AS job_id,
    s.department_id,
    s.status,
    s.issue_date,
    s.due_date,
    s.currency,
    s.amount,
    s.tax_amount,
    s.description,
    s.added_by,
    s.created_at
FROM {{ ref('stg_purchase_orders') }} s
