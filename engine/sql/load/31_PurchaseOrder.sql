USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.PurchaseOrder;

INSERT INTO dbo.PurchaseOrder (
    PONo,
    CompanyID,
    PODate,
    POAmount,
    Status,
    AddedAt,
    AddedBy
)
SELECT
    po.po_no                                                 AS PONo,
    po.client_id                                             AS CompanyID,
    po.issue_date                                            AS PODate,
    po.amount                                                AS POAmount,
    UPPER(LEFT(po.status, 1)) + SUBSTRING(po.status, 2, 50)  AS Status,
    po.created_at                                            AS AddedAt,
    po.added_by                                              AS AddedBy
FROM Migration_Staging.mid.PurchaseOrders po;
