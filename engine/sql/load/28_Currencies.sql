USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Currencies;

INSERT INTO dbo.Currencies (
    CurrencyID,
    CurrencyCode
)
SELECT
    ROW_NUMBER() OVER (ORDER BY cu.currency)  AS CurrencyID,
    cu.currency                               AS CurrencyCode
FROM (SELECT DISTINCT currency FROM Migration_Staging.mid.Invoices WHERE currency IS NOT NULL) cu;
