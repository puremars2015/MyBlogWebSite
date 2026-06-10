USE BlogShopDB;
DELETE FROM products WHERE id = 99;
INSERT INTO products (id, slug, name, description, price, stock, category_id)
VALUES (99, 'test-cn', N'有田燒', N'中文測試 400年', 1.0, 1, 2);
SELECT id, name, description FROM products WHERE id = 99;
