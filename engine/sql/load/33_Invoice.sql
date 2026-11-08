USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Invoice;

INSERT INTO dbo.Invoice (
    ID,
    Type,
    InvoiceNo,
    PlacementID,
    Amount,
    TaxAmount,
    Currency,
    InvoiceDate,
    DueDate,
    Status,
    Notes,
    AddedBy
)
SELECT
    TRY_CAST(inv.invoice_id AS INT)                                                                                                                              AS ID,
    inv.invoice_type                                                                                                                                             AS Type,
    inv.invoice_no                                                                                                                                               AS InvoiceNo,
    (SELECT TOP 1 TRY_CAST(l.placement_id AS INT) FROM Migration_Staging.mid.InvoiceLines l WHERE l.invoice_id = inv.invoice_id AND l.placement_id IS NOT NULL)  AS PlacementID,
    inv.net_amount                                                                                                                                               AS Amount,
    inv.vat_amount                                                                                                                                               AS TaxAmount,
    inv.currency                                                                                                                                                 AS Currency,
    inv.invoice_date                                                                                                                                             AS InvoiceDate,
    inv.due_date                                                                                                                                                 AS DueDate,
    UPPER(LEFT(inv.status, 1)) + SUBSTRING(inv.status, 2, 50)                                                                                                    AS Status,
    inv.description                                                                                                                                              AS Notes,
    inv.added_by                                                                                                                                                 AS AddedBy
FROM Migration_Staging.mid.Invoices inv;
