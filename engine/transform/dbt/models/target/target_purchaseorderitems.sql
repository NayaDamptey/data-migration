{{ config(alias='PurchaseOrderItems') }}
SELECT
    TRY_CAST(ROW_NUMBER() OVER (ORDER BY po.po_no NULLS FIRST) AS INTEGER) AS ID,
    TRY_CAST(po.po_no AS VARCHAR) AS PONo,
    TRY_CAST(TRY_CAST(po.job_id AS INT) AS INTEGER) AS PositionID,
    TRY_CAST(po.description AS VARCHAR) AS Description,
    TRY_CAST(1 AS INTEGER) AS Quantity,
    TRY_CAST(po.amount AS DECIMAL(8,2)) AS UnitPrice,
    TRY_CAST(po.amount AS DECIMAL(8,2)) AS Amount,
    TRY_CAST(UPPER(LEFT(CAST(po.status AS TEXT), 1)) || SUBSTRING(po.status, 2, 50) AS VARCHAR) AS Status,
    TRY_CAST(po.added_by AS VARCHAR) AS AddedBy,
    TRY_CAST(po.created_at AS TIMESTAMP) AS AddedAt
FROM {{ ref('mid_purchase_orders') }} AS po
