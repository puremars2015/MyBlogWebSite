USE BlogShopDB;
GO

IF OBJECT_ID('dbo.schema_migrations', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.schema_migrations (
        name NVARCHAR(200) PRIMARY KEY,
        applied_at DATETIME NOT NULL DEFAULT DATEADD(HOUR, 8, GETUTCDATE())
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE name = N'20260616_gmt8_unification')
BEGIN
    DECLARE @drop_sql NVARCHAR(MAX) = N'';

    SELECT @drop_sql = @drop_sql +
        N'ALTER TABLE ' + QUOTENAME(SCHEMA_NAME(t.schema_id)) + N'.' + QUOTENAME(t.name) +
        N' DROP CONSTRAINT ' + QUOTENAME(dc.name) + N';'
    FROM sys.default_constraints dc
    JOIN sys.tables t ON dc.parent_object_id = t.object_id
    JOIN sys.columns c ON c.object_id = t.object_id AND c.column_id = dc.parent_column_id
    WHERE t.name IN (N'members', N'posts', N'products', N'orders', N'admins')
      AND c.name IN (N'created_at', N'updated_at');

    IF LEN(@drop_sql) > 0
    BEGIN
        EXEC sp_executesql @drop_sql;
    END

    IF OBJECT_ID('dbo.members', 'U') IS NOT NULL
    BEGIN
        ALTER TABLE dbo.members ADD CONSTRAINT DF_members_created_at_gmt8 DEFAULT DATEADD(HOUR, 8, GETUTCDATE()) FOR created_at;
        ALTER TABLE dbo.members ADD CONSTRAINT DF_members_updated_at_gmt8 DEFAULT DATEADD(HOUR, 8, GETUTCDATE()) FOR updated_at;
        UPDATE dbo.members
        SET created_at = DATEADD(HOUR, 8, created_at),
            updated_at = DATEADD(HOUR, 8, updated_at),
            last_login_at = CASE WHEN last_login_at IS NULL THEN NULL ELSE DATEADD(HOUR, 8, last_login_at) END,
            locked_until = CASE WHEN locked_until IS NULL THEN NULL ELSE DATEADD(HOUR, 8, locked_until) END;
    END

    IF OBJECT_ID('dbo.posts', 'U') IS NOT NULL
    BEGIN
        ALTER TABLE dbo.posts ADD CONSTRAINT DF_posts_created_at_gmt8 DEFAULT DATEADD(HOUR, 8, GETUTCDATE()) FOR created_at;
        ALTER TABLE dbo.posts ADD CONSTRAINT DF_posts_updated_at_gmt8 DEFAULT DATEADD(HOUR, 8, GETUTCDATE()) FOR updated_at;
        UPDATE dbo.posts
        SET created_at = DATEADD(HOUR, 8, created_at),
            updated_at = DATEADD(HOUR, 8, updated_at);
    END

    IF OBJECT_ID('dbo.products', 'U') IS NOT NULL
    BEGIN
        ALTER TABLE dbo.products ADD CONSTRAINT DF_products_created_at_gmt8 DEFAULT DATEADD(HOUR, 8, GETUTCDATE()) FOR created_at;
        ALTER TABLE dbo.products ADD CONSTRAINT DF_products_updated_at_gmt8 DEFAULT DATEADD(HOUR, 8, GETUTCDATE()) FOR updated_at;
        UPDATE dbo.products
        SET created_at = DATEADD(HOUR, 8, created_at),
            updated_at = DATEADD(HOUR, 8, updated_at);
    END

    IF OBJECT_ID('dbo.orders', 'U') IS NOT NULL
    BEGIN
        ALTER TABLE dbo.orders ADD CONSTRAINT DF_orders_created_at_gmt8 DEFAULT DATEADD(HOUR, 8, GETUTCDATE()) FOR created_at;
        ALTER TABLE dbo.orders ADD CONSTRAINT DF_orders_updated_at_gmt8 DEFAULT DATEADD(HOUR, 8, GETUTCDATE()) FOR updated_at;
        UPDATE dbo.orders
        SET created_at = DATEADD(HOUR, 8, created_at),
            updated_at = DATEADD(HOUR, 8, updated_at);
    END

    IF OBJECT_ID('dbo.admins', 'U') IS NOT NULL
    BEGIN
        ALTER TABLE dbo.admins ADD CONSTRAINT DF_admins_created_at_gmt8 DEFAULT DATEADD(HOUR, 8, GETUTCDATE()) FOR created_at;
        ALTER TABLE dbo.admins ADD CONSTRAINT DF_admins_updated_at_gmt8 DEFAULT DATEADD(HOUR, 8, GETUTCDATE()) FOR updated_at;
        UPDATE dbo.admins
        SET created_at = DATEADD(HOUR, 8, created_at),
            updated_at = DATEADD(HOUR, 8, updated_at),
            last_login_at = CASE WHEN last_login_at IS NULL THEN NULL ELSE DATEADD(HOUR, 8, last_login_at) END,
            locked_until = CASE WHEN locked_until IS NULL THEN NULL ELSE DATEADD(HOUR, 8, locked_until) END;
    END

    IF OBJECT_ID('dbo.economic_series', 'U') IS NOT NULL
    BEGIN
        UPDATE dbo.economic_series
        SET created_at = DATEADD(HOUR, 8, created_at),
            updated_at = DATEADD(HOUR, 8, updated_at);
    END

    IF OBJECT_ID('dbo.economic_observations', 'U') IS NOT NULL
    BEGIN
        UPDATE dbo.economic_observations
        SET observed_at = DATEADD(HOUR, 8, observed_at),
            created_at = DATEADD(HOUR, 8, created_at);
    END

    IF OBJECT_ID('dbo.economic_events', 'U') IS NOT NULL
    BEGIN
        UPDATE dbo.economic_events
        SET event_at = DATEADD(HOUR, 8, event_at),
            created_at = DATEADD(HOUR, 8, created_at),
            updated_at = DATEADD(HOUR, 8, updated_at);
    END

    IF OBJECT_ID('dbo.economic_fetch_jobs', 'U') IS NOT NULL
    BEGIN
        UPDATE dbo.economic_fetch_jobs
        SET next_run_at = CASE WHEN next_run_at IS NULL THEN NULL ELSE DATEADD(HOUR, 8, next_run_at) END,
            last_run_at = CASE WHEN last_run_at IS NULL THEN NULL ELSE DATEADD(HOUR, 8, last_run_at) END,
            created_at = DATEADD(HOUR, 8, created_at),
            updated_at = DATEADD(HOUR, 8, updated_at);
    END

    IF OBJECT_ID('dbo.economic_fetch_runs', 'U') IS NOT NULL
    BEGIN
        UPDATE dbo.economic_fetch_runs
        SET started_at = DATEADD(HOUR, 8, started_at),
            finished_at = CASE WHEN finished_at IS NULL THEN NULL ELSE DATEADD(HOUR, 8, finished_at) END;
    END

    INSERT INTO dbo.schema_migrations (name) VALUES (N'20260616_gmt8_unification');
END
GO