-- 建立資料庫
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'BlogShopDB')
BEGIN
    CREATE DATABASE BlogShopDB;
END
GO

USE BlogShopDB;
GO

-- 部落格相關表格
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'posts')
BEGIN
    CREATE TABLE posts (
        id INT PRIMARY KEY IDENTITY(1,1),
        title NVARCHAR(200) NOT NULL,
        content TEXT NOT NULL,
        created_at DATETIME DEFAULT GETDATE()
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'categories')
BEGIN
    CREATE TABLE categories (
        id INT PRIMARY KEY IDENTITY(1,1),
        name NVARCHAR(100) NOT NULL,
        description NVARCHAR(500)
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'tags')
BEGIN
    CREATE TABLE tags (
        id INT PRIMARY KEY IDENTITY(1,1),
        name NVARCHAR(50) NOT NULL
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'post_tags')
BEGIN
    CREATE TABLE post_tags (
        post_id INT REFERENCES posts(id),
        tag_id INT REFERENCES tags(id),
        PRIMARY KEY (post_id, tag_id)
    );
END

-- 商城相關表格
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'products')
BEGIN
    CREATE TABLE products (
        id INT PRIMARY KEY IDENTITY(1,1),
        name NVARCHAR(200) NOT NULL,
        price DECIMAL(10, 2) NOT NULL,
        description TEXT,
        stock INT DEFAULT 0,
        created_at DATETIME DEFAULT GETDATE()
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'members')
BEGIN
    CREATE TABLE members (
        id INT PRIMARY KEY IDENTITY(1,1),
        username NVARCHAR(100) NOT NULL UNIQUE,
        email NVARCHAR(200) NOT NULL UNIQUE,
        password_hash NVARCHAR(255) NOT NULL,
        created_at DATETIME DEFAULT GETDATE()
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'orders')
BEGIN
    CREATE TABLE orders (
        id INT PRIMARY KEY IDENTITY(1,1),
        member_id INT REFERENCES members(id),
        product_id INT REFERENCES products(id),
        quantity INT NOT NULL,
        total_price DECIMAL(10, 2) NOT NULL,
        status NVARCHAR(50) DEFAULT 'pending',
        created_at DATETIME DEFAULT GETDATE()
    );
END

-- 插入範例資料
IF NOT EXISTS (SELECT * FROM posts)
BEGIN
    INSERT INTO posts (title, content) VALUES
    ('第一篇文章', '這是部落格的第一篇文章內容。'),
    ('第二篇文章', '這是部落格的第二篇文章內容。');
END

IF NOT EXISTS (SELECT * FROM products)
BEGIN
    INSERT INTO products (name, price, description, stock) VALUES
    ('範例商品 1', 99.99, '這是範例商品的描述', 100),
    ('範例商品 2', 149.99, '這是另一個範例商品', 50);
END

PRINT '資料庫初始化完成';
GO