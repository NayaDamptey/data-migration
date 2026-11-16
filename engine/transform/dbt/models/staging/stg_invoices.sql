-- generated from spec/middle.yml: source -> canonical shape
SELECT
    TRY_CAST(inv.InvoiceID AS VARCHAR) AS invoice_id,
    TRY_CAST(inv.Invoice_No AS VARCHAR) AS invoice_no,
    TRY_CAST(inv.PONo AS VARCHAR) AS po_no,
    TRY_CAST(inv.Vendor_ID AS VARCHAR) AS client_id,
    TRY_CAST(it.Type_Name AS VARCHAR) AS invoice_type,
    TRY_CAST(LOWER(inv.Status) AS VARCHAR) AS status,
    TRY_CAST(inv.Currency AS VARCHAR) AS currency,
    TRY_CAST(inv.NETAmount AS DECIMAL(12,2)) AS net_amount,
    TRY_CAST(inv.Amount - inv.NETAmount AS DECIMAL(12,2)) AS vat_amount,
    TRY_CAST(inv.Amount AS DECIMAL(12,2)) AS gross_amount,
    TRY_CAST(CAST(inv.InvoiceDate AS DATE) AS DATE) AS invoice_date,
    TRY_CAST(CAST(inv.DateDue AS DATE) AS DATE) AS due_date,
    TRY_CAST(inv."Desc" AS VARCHAR) AS description,
    TRY_CAST(inv.CreatedBy AS VARCHAR) AS added_by
FROM {{ source('legacy', 'Invoice') }} AS inv
LEFT JOIN {{ source('legacy', 'InvoiceTypes') }} AS it ON it.InvoiceType_ID = inv.InvoiceType_ID
