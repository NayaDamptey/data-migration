/* =============================================================================
   00_install_profiling.sql  —  generic profiling procedures (schema: dq)
   Target: Cobaltdesk_Legacy (SQL Server 2017+)

   Installs:
     dq.usp_ColumnProfile  @Table = NULL   -> completeness / cardinality / length / min-max per column
     dq.usp_OrphanCheck                    -> orphan rows for every FK (disabled/untrusted FKs can hide them)
     dq.usp_EncodingCheck                  -> mojibake (Â£, â€™, Ã©...) in every text column

   Run once (re-run after rebuilding the DB):
     sqlcmd -S "localhost\SQLEXPRESS" -E -i sql\profiling\00_install_profiling.sql
   or in DBeaver: open this file and Execute Script (Alt+X)  — each batch is separated by GO.
   ========================================================================== */
USE Cobaltdesk_Legacy;
GO
IF SCHEMA_ID(N'dq') IS NULL EXEC (N'CREATE SCHEMA dq AUTHORIZATION dbo');
GO

/* ---------------------------------------------------------------------------
   dq.usp_ColumnProfile
   One row per column: rows, NULLs, blanks (strings), % populated, distinct
   values, min/max length, min/max value.
   --------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE dq.usp_ColumnProfile
    @Table sysname = NULL          -- NULL = every dbo table
AS
BEGIN
    SET NOCOUNT ON;
    -- One statement per table, collected into a temp table. (A single UNION ALL over all
    -- ~540 columns takes minutes just to compile once the FK indexes exist.)
    CREATE TABLE #profile (
        table_name sysname, column_name sysname, data_type nvarchar(40), row_count bigint,
        null_count bigint, blank_count bigint, pct_populated decimal(5,1), distinct_count bigint,
        min_len int, max_len int, min_value nvarchar(60), max_value nvarchar(60), column_id int);
    DECLARE @stmts TABLE (ord int IDENTITY, stmt nvarchar(max));

    INSERT INTO @stmts (stmt)
    SELECT N'INSERT INTO #profile ' + STRING_AGG(CAST(col_sql AS nvarchar(max)), N' UNION ALL ')
                                       WITHIN GROUP (ORDER BY column_id)
    FROM (
    SELECT t.name AS table_name, c.column_id,
        N'SELECT ' + QUOTENAME(t.name, '''') + N' AS table_name, '
        + QUOTENAME(c.name, '''') + N' AS column_name, '
        + QUOTENAME(ty.name + CASE WHEN ty.name IN ('nvarchar','varchar') THEN '(' +
              CASE WHEN c.max_length = -1 THEN 'MAX' ELSE CAST(c.max_length / CASE WHEN ty.name = 'nvarchar' THEN 2 ELSE 1 END AS varchar(10)) END + ')'
              WHEN ty.name = 'decimal' THEN '(' + CAST(c.precision AS varchar(3)) + ',' + CAST(c.scale AS varchar(3)) + ')' ELSE '' END, '''') + N' AS data_type, '
        + N'COUNT_BIG(*) AS row_count, '
        + N'SUM(CASE WHEN ' + QUOTENAME(c.name) + N' IS NULL THEN 1 ELSE 0 END) AS null_count, '
        + CASE WHEN ty.name IN ('nvarchar','varchar','nchar','char')
               THEN N'SUM(CASE WHEN LTRIM(RTRIM(' + QUOTENAME(c.name) + N')) = N'''' THEN 1 ELSE 0 END)'
               ELSE N'0' END + N' AS blank_count, '
        + N'CAST(100.0 * COUNT(' + QUOTENAME(c.name) + N') / NULLIF(COUNT_BIG(*), 0) AS decimal(5,1)) AS pct_populated, '
        + N'COUNT(DISTINCT ' + CASE WHEN ty.name = 'bit' THEN N'CAST(' + QUOTENAME(c.name) + N' AS int)'
                                    WHEN c.max_length = -1 THEN N'LEFT(' + QUOTENAME(c.name) + N', 4000)'
                                    ELSE QUOTENAME(c.name) END + N') AS distinct_count, '
        + CASE WHEN ty.name IN ('nvarchar','varchar','nchar','char')
               THEN N'MIN(LEN(' + QUOTENAME(c.name) + N')) AS min_len, MAX(LEN(' + QUOTENAME(c.name) + N')) AS max_len, '
               ELSE N'NULL AS min_len, NULL AS max_len, ' END
        + N'CAST(MIN(' + CASE WHEN ty.name = 'bit' THEN N'CAST(' + QUOTENAME(c.name) + N' AS int)'
                              WHEN c.max_length = -1 THEN N'LEFT(' + QUOTENAME(c.name) + N', 60)'
                              ELSE QUOTENAME(c.name) END + N') AS nvarchar(60)) AS min_value, '
        + N'CAST(MAX(' + CASE WHEN ty.name = 'bit' THEN N'CAST(' + QUOTENAME(c.name) + N' AS int)'
                              WHEN c.max_length = -1 THEN N'LEFT(' + QUOTENAME(c.name) + N', 60)'
                              ELSE QUOTENAME(c.name) END + N') AS nvarchar(60)) AS max_value, '
        + CAST(c.column_id AS nvarchar(10)) + N' AS column_id '
        + N'FROM dbo.' + QUOTENAME(t.name) AS col_sql
    FROM sys.tables t
    JOIN sys.columns c  ON c.object_id = t.object_id
    JOIN sys.types   ty ON ty.user_type_id = c.user_type_id
    WHERE SCHEMA_NAME(t.schema_id) = N'dbo'
      AND (@Table IS NULL OR t.name = @Table)
    ) per_column
    GROUP BY table_name;            -- one statement per table

    IF NOT EXISTS (SELECT 1 FROM @stmts) BEGIN RAISERROR('No such table: %s', 16, 1, @Table); RETURN; END;

    DECLARE @i int = 1, @n int = (SELECT MAX(ord) FROM @stmts), @sql nvarchar(max);
    WHILE @i <= @n
    BEGIN
        SELECT @sql = stmt FROM @stmts WHERE ord = @i;
        EXEC sys.sp_executesql @sql;
        SET @i += 1;
    END;

    SELECT table_name, column_name, data_type, row_count, null_count, blank_count, pct_populated,
           distinct_count, min_len, max_len, min_value, max_value
    FROM #profile ORDER BY table_name, column_id;
END;
GO

/* ---------------------------------------------------------------------------
   dq.usp_OrphanCheck
   For every single-column FK: how many child rows point at a missing parent.
   A trusted FK guarantees 0; disabled / untrusted ones are where orphans hide.
   --------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE dq.usp_OrphanCheck
    @OnlyProblems bit = 1          -- 1 = only FKs with orphans or not trusted
AS
BEGIN
    SET NOCOUNT ON;
    CREATE TABLE #orphans (fk_name sysname, child_table sysname, child_column sysname, parent_table sysname,
                           parent_column sysname, is_disabled bit, is_not_trusted bit, orphan_rows int,
                           sample_values nvarchar(200));
    DECLARE @stmts TABLE (ord int IDENTITY, stmt nvarchar(max));

    -- one small statement per FK (a single UNION ALL over all FKs is slow / memory-hungry to compile)
    INSERT INTO @stmts (stmt)
    SELECT N'INSERT INTO #orphans SELECT ' + QUOTENAME(fk.name, '''') + N', '
        + QUOTENAME(OBJECT_NAME(fk.parent_object_id), '''') + N', ' + QUOTENAME(pc.name, '''') + N', '
        + QUOTENAME(OBJECT_NAME(fk.referenced_object_id), '''') + N', ' + QUOTENAME(rc.name, '''') + N', '
        + CAST(fk.is_disabled AS nchar(1)) + N', ' + CAST(fk.is_not_trusted AS nchar(1)) + N', '
        + N'COUNT(*), LEFT(STRING_AGG(CAST(c.' + QUOTENAME(pc.name) + N' AS nvarchar(max)), N'', ''), 200) '
        + N'FROM dbo.' + QUOTENAME(OBJECT_NAME(fk.parent_object_id)) + N' c '
        + N'WHERE c.' + QUOTENAME(pc.name) + N' IS NOT NULL AND NOT EXISTS (SELECT 1 FROM dbo.'
        + QUOTENAME(OBJECT_NAME(fk.referenced_object_id)) + N' p WHERE p.' + QUOTENAME(rc.name)
        + N' = c.' + QUOTENAME(pc.name) + N')'
    FROM sys.foreign_keys fk
    JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
    JOIN sys.columns pc ON pc.object_id = fkc.parent_object_id     AND pc.column_id = fkc.parent_column_id
    JOIN sys.columns rc ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id
    WHERE (SELECT COUNT(*) FROM sys.foreign_key_columns x WHERE x.constraint_object_id = fk.object_id) = 1;

    DECLARE @i int = 1, @n int = (SELECT MAX(ord) FROM @stmts), @sql nvarchar(max);
    WHILE @i <= @n
    BEGIN
        SELECT @sql = stmt FROM @stmts WHERE ord = @i;
        EXEC sys.sp_executesql @sql;
        SET @i += 1;
    END;

    SELECT * FROM #orphans
    WHERE @OnlyProblems = 0 OR orphan_rows > 0 OR is_not_trusted = 1
    ORDER BY orphan_rows DESC, child_table;
END;
GO

/* ---------------------------------------------------------------------------
   dq.usp_EncodingCheck
   Text columns containing UTF-8-read-as-Windows-1252 artefacts.
   --------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE dq.usp_EncodingCheck
AS
BEGIN
    SET NOCOUNT ON;
    CREATE TABLE #hits (table_name sysname, column_name sysname, pk_value nvarchar(50), sample_text nvarchar(150));
    DECLARE @stmts TABLE (ord int IDENTITY, stmt nvarchar(max));

    -- one statement per text column (a single UNION ALL over every column compiles very slowly)
    INSERT INTO @stmts (stmt)
    SELECT N'INSERT INTO #hits SELECT ' + QUOTENAME(t.name, '''') + N', ' + QUOTENAME(c.name, '''') + N', '
        + N'CAST(' + QUOTENAME(pk.name) + N' AS nvarchar(50)), LEFT(' + QUOTENAME(c.name) + N', 150) FROM dbo.' + QUOTENAME(t.name)
        + N' WHERE ' + QUOTENAME(c.name) + N' LIKE N''%Â%'' OR ' + QUOTENAME(c.name) + N' LIKE N''%â€%'' OR '
        + QUOTENAME(c.name) + N' LIKE N''%Ã%'' OR ' + QUOTENAME(c.name)
        -- U+FFFD has no sort weight in the default collation (would match every row): compare in binary
        + N' COLLATE Latin1_General_BIN LIKE N''%' + NCHAR(65533) + N'%'''
    FROM sys.tables t
    JOIN sys.columns c  ON c.object_id = t.object_id
    JOIN sys.types   ty ON ty.user_type_id = c.user_type_id
    CROSS APPLY (SELECT TOP 1 col.name
                 FROM sys.indexes i
                 JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
                 JOIN sys.columns col ON col.object_id = ic.object_id AND col.column_id = ic.column_id
                 WHERE i.object_id = t.object_id AND i.is_primary_key = 1) pk
    WHERE SCHEMA_NAME(t.schema_id) = N'dbo' AND ty.name IN ('nvarchar','varchar','nchar','char');

    DECLARE @i int = 1, @n int = (SELECT MAX(ord) FROM @stmts), @sql nvarchar(max);
    WHILE @i <= @n
    BEGIN
        SELECT @sql = stmt FROM @stmts WHERE ord = @i;
        EXEC sys.sp_executesql @sql;
        SET @i += 1;
    END;

    SELECT * FROM #hits ORDER BY table_name, column_name;
END;
GO
PRINT 'dq profiling procedures installed';
GO
