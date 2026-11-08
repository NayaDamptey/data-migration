USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.PurchaseOrderItems;

INSERT INTO dbo.PurchaseOrderItems (
    ID,
    PONo,
    PositionID,
    Description,
    Quantity,
    UnitPrice,
    Amount,
    Status,
    AddedBy,
    AddedAt
)
SELECT
    ROW_NUMBER() OVER (ORDER BY po.po_no)                    AS ID,
    po.po_no                                                 AS PONo,
    TRY_CAST(po.job_id AS INT)                               AS PositionID,
    po.description                                           AS Description,
    1                                                        AS Quantity,
    po.amount                                                AS UnitPrice,
    po.amount                                                AS Amount,
    UPPER(LEFT(po.status, 1)) + SUBSTRING(po.status, 2, 50)  AS Status,
    po.added_by                                              AS AddedBy,
    po.created_at                                            AS AddedAt
FROM Migration_Staging.mid.PurchaseOrders po;
