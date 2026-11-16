{{ config(alias='PurchaseOrder') }}
SELECT
    TRY_CAST(po.po_no AS VARCHAR) AS PONo,
    TRY_CAST(po.client_id AS VARCHAR) AS CompanyID,
    TRY_CAST(po.issue_date AS DATE) AS PODate,
    TRY_CAST(po.amount AS DECIMAL(8,2)) AS POAmount,
    TRY_CAST(UPPER(LEFT(CAST(po.status AS TEXT), 1)) || SUBSTRING(po.status, 2, 50) AS VARCHAR) AS Status,
    TRY_CAST(po.created_at AS TIMESTAMP) AS AddedAt,
    TRY_CAST(po.added_by AS VARCHAR) AS AddedBy
FROM {{ ref('mid_purchase_orders') }} AS po
