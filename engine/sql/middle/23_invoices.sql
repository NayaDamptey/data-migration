USE Migration_Staging;

TRUNCATE TABLE mid.Invoices;

INSERT INTO mid.Invoices (
    invoice_id,
    invoice_no,
    po_no,
    client_id,
    invoice_type,
    status,
    currency,
    net_amount,
    vat_amount,
    gross_amount,
    invoice_date,
    due_date,
    description,
    added_by
)
SELECT
    inv.InvoiceID                  AS invoice_id,
    inv.Invoice_No                 AS invoice_no,
    inv.PONo                       AS po_no,
    inv.Vendor_ID                  AS client_id,
    it.Type_Name                   AS invoice_type,
    LOWER(inv.Status)              AS status,
    inv.Currency                   AS currency,
    inv.NETAmount                  AS net_amount,
    inv.Amount - inv.NETAmount     AS vat_amount,
    inv.Amount                     AS gross_amount,
    CAST(inv.InvoiceDate AS DATE)  AS invoice_date,
    CAST(inv.DateDue AS DATE)      AS due_date,
    inv.[Desc]                     AS description,
    inv.CreatedBy                  AS added_by
FROM Cobaltdesk_Legacy.dbo.Invoice inv
LEFT JOIN Cobaltdesk_Legacy.dbo.InvoiceTypes it ON it.InvoiceType_ID = inv.InvoiceType_ID;
