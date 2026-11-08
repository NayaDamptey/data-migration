USE Migration_Staging;

TRUNCATE TABLE mid.PurchaseOrders;

INSERT INTO mid.PurchaseOrders (
    po_no,
    client_id,
    job_id,
    department_id,
    status,
    issue_date,
    due_date,
    currency,
    amount,
    tax_amount,
    description,
    added_by,
    created_at
)
SELECT
    po.PONo                      AS po_no,
    po.VendorID                  AS client_id,
    po.ReqID                     AS job_id,
    po.DepartmentID              AS department_id,
    LOWER(po.POStatus)           AS status,
    CAST(po.Issue_Date AS DATE)  AS issue_date,
    CAST(po.DateDue AS DATE)     AS due_date,
    po.Currency                  AS currency,
    po.Amount                    AS amount,
    po.TaxAmount                 AS tax_amount,
    po.[Desc]                    AS description,
    po.CreatedBy                 AS added_by,
    po.CreatedAt                 AS created_at
FROM Cobaltdesk_Legacy.dbo.PONo po;
