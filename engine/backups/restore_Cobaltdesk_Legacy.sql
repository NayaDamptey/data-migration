/* =============================================================================
   restore_Cobaltdesk_Legacy.sql
   Restores backups/Cobaltdesk_Legacy.bak (legacy recruitment CRM source DB:
   58 tables, 156 FKs (8 disabled), 242 planted data-quality defects, dq.* profiling procs).

   Requirements
     * SQL Server 2022 or later (any edition, incl. Express / Developer).
       A 2022 backup cannot be restored on 2019 or older.
     * The .bak must be readable by the SQL Server SERVICE account. Simplest:
       copy it into the server's Backup folder, e.g.
       C:\Program Files\Microsoft SQL Server\MSSQL16.SQLEXPRESS\MSSQL\Backup\

   Run
     sqlcmd -S "localhost\SQLEXPRESS" -E -i backups\restore_Cobaltdesk_Legacy.sql
     or open in SSMS / DBeaver and execute (edit @BakFile / @DbName first).
   ========================================================================== */
SET NOCOUNT ON;

DECLARE @BakFile  nvarchar(400) = CAST(SERVERPROPERTY('InstanceDefaultBackupPath') AS nvarchar(300)) + N'\Cobaltdesk_Legacy.bak';
DECLARE @DbName   sysname       = N'Cobaltdesk_Legacy';
DECLARE @DataPath nvarchar(400) = CAST(SERVERPROPERTY('InstanceDefaultDataPath') AS nvarchar(400));
DECLARE @LogPath  nvarchar(400) = CAST(SERVERPROPERTY('InstanceDefaultLogPath')  AS nvarchar(400));

IF DB_ID(@DbName) IS NOT NULL
    EXEC (N'ALTER DATABASE ' + N'[' + @DbName + N'] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;');

DECLARE @sql nvarchar(max) =
    N'RESTORE DATABASE ' + QUOTENAME(@DbName) + N' FROM DISK = N''' + @BakFile + N''' WITH REPLACE, CHECKSUM, RECOVERY, STATS = 25, '
  + N'MOVE N''Cobaltdesk_Legacy''     TO N''' + @DataPath + @DbName + N'.mdf'', '
  + N'MOVE N''Cobaltdesk_Legacy_log'' TO N''' + @LogPath  + @DbName + N'_log.ldf'';';
PRINT @sql;
EXEC sys.sp_executesql @sql;

EXEC (N'ALTER DATABASE ' + N'[' + @DbName + N'] SET MULTI_USER; ALTER DATABASE [' + @DbName + N'] SET AUTO_CLOSE OFF;');

-- quick sanity check
EXEC (N'SELECT (SELECT COUNT(*) FROM ' + N'[' + @DbName + N'].sys.tables WHERE schema_id = SCHEMA_ID(''dbo'')) AS tables,
             (SELECT COUNT(*) FROM [' + @DbName + N'].sys.foreign_keys) AS foreign_keys,
             (SELECT COUNT(*) FROM [' + @DbName + N'].dbo.Person) AS person_rows,
             (SELECT COUNT(*) FROM [' + @DbName + N'].dbo.Accounts) AS account_rows;');
