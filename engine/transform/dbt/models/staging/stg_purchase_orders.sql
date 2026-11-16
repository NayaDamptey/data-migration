SELECT
    TRY_CAST(po.PONo AS VARCHAR) AS po_no,
    TRY_CAST(po.VendorID AS VARCHAR) AS client_id,
    TRY_CAST(po.ReqID AS VARCHAR) AS job_id,
    TRY_CAST(po.DepartmentID AS VARCHAR) AS department_id,
    TRY_CAST(LOWER(po.POStatus) AS VARCHAR) AS status,
    TRY_CAST(CAST(po.Issue_Date AS DATE) AS DATE) AS issue_date,
    TRY_CAST(CAST(po.DateDue AS DATE) AS DATE) AS due_date,
    TRY_CAST(po.Currency AS VARCHAR) AS currency,
    TRY_CAST(po.Amount AS DECIMAL(12,2)) AS amount,
    TRY_CAST(po.TaxAmount AS DECIMAL(12,2)) AS tax_amount,
    TRY_CAST(po."Desc" AS VARCHAR) AS description,
    TRY_CAST(po.CreatedBy AS VARCHAR) AS added_by,
    TRY_CAST(po.CreatedAt AS TIMESTAMP) AS created_at
FROM {{ source('legacy', 'PONo') }} AS po
