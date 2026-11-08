USE Migration_Staging;

TRUNCATE TABLE mid.InvoiceLines;

INSERT INTO mid.InvoiceLines (
    line_id,
    invoice_id,
    placement_id,
    description,
    quantity,
    unit_price,
    amount,
    created_at
)
SELECT
    ie.Invoice_EntryID  AS line_id,
    ie.Invoice_ID       AS invoice_id,
    ie.Plac_ID          AS placement_id,
    ie.[Desc]           AS description,
    ie.Quantity         AS quantity,
    ie.Unit_Price       AS unit_price,
    ie.Amount           AS amount,
    ie.CreatedAt        AS created_at
FROM Cobaltdesk_Legacy.dbo.InvoiceEntries ie;
