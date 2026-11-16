-- generated from spec/middle.yml: source -> canonical shape
SELECT
    TRY_CAST(ie.Invoice_EntryID AS VARCHAR) AS line_id,
    TRY_CAST(ie.Invoice_ID AS VARCHAR) AS invoice_id,
    TRY_CAST(ie.Plac_ID AS VARCHAR) AS placement_id,
    TRY_CAST(ie."Desc" AS VARCHAR) AS description,
    TRY_CAST(ie.Quantity AS DECIMAL(12,2)) AS quantity,
    TRY_CAST(ie.Unit_Price AS DECIMAL(12,2)) AS unit_price,
    TRY_CAST(ie.Amount AS DECIMAL(12,2)) AS amount,
    TRY_CAST(ie.CreatedAt AS TIMESTAMP) AS created_at
FROM {{ source('legacy', 'InvoiceEntries') }} AS ie
