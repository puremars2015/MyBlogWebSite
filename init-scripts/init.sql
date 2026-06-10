-- ============================================================
-- 拾光選物 — 初始化腳本
-- 對應 schema 規劃見 內容規劃.md §4
-- 對應 API 端點見 blog/app.py / shop/app.py
-- ============================================================

-- 建立資料庫
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'BlogShopDB')
BEGIN
    CREATE DATABASE BlogShopDB;
END
GO

USE BlogShopDB;
GO

-- ============================================================
-- 1. 部落格分類
-- ============================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'categories')
BEGIN
    CREATE TABLE categories (
        id INT PRIMARY KEY IDENTITY(1,1),
        slug NVARCHAR(80) UNIQUE NOT NULL,
        name NVARCHAR(100) NOT NULL,
        description NVARCHAR(500)
    );
END
GO

-- ============================================================
-- 2. 商品分類(與文章分類分開管理)
-- ============================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'product_categories')
BEGIN
    CREATE TABLE product_categories (
        id INT PRIMARY KEY IDENTITY(1,1),
        slug NVARCHAR(80) UNIQUE NOT NULL,
        name NVARCHAR(100) NOT NULL,
        description NVARCHAR(500),
        sort_order INT DEFAULT 0
    );
END
GO

-- ============================================================
-- 3. 標籤
-- ============================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'tags')
BEGIN
    CREATE TABLE tags (
        id INT PRIMARY KEY IDENTITY(1,1),
        name NVARCHAR(50) NOT NULL UNIQUE
    );
END
GO

-- ============================================================
-- 4. 會員
-- ============================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'members')
BEGIN
    CREATE TABLE members (
        id INT PRIMARY KEY IDENTITY(1,1),
        username NVARCHAR(100) NOT NULL UNIQUE,
        email NVARCHAR(200) NOT NULL UNIQUE,
        display_name NVARCHAR(100),
        password_hash NVARCHAR(255) NOT NULL,
        avatar_url NVARCHAR(500),
        bio NVARCHAR(MAX),
        is_active BIT DEFAULT 1,
        last_login_at DATETIME,
        failed_login_count INT DEFAULT 0,
        locked_until DATETIME,
        created_at DATETIME DEFAULT GETDATE(),
        updated_at DATETIME DEFAULT GETDATE()
    );
END
GO

-- 補上既有 members 表可能缺少的欄位(給老 volume 升級用)
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('members') AND name = 'avatar_url')
    ALTER TABLE members ADD avatar_url NVARCHAR(500);
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('members') AND name = 'bio')
    ALTER TABLE members ADD bio NVARCHAR(MAX);
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('members') AND name = 'is_active')
    ALTER TABLE members ADD is_active BIT DEFAULT 1;
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('members') AND name = 'last_login_at')
    ALTER TABLE members ADD last_login_at DATETIME;
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('members') AND name = 'failed_login_count')
    ALTER TABLE members ADD failed_login_count INT DEFAULT 0;
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('members') AND name = 'locked_until')
    ALTER TABLE members ADD locked_until DATETIME;
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('members') AND name = 'updated_at')
    ALTER TABLE members ADD updated_at DATETIME DEFAULT GETDATE();
GO

-- ============================================================
-- 5. 文章
-- ============================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'posts')
BEGIN
    CREATE TABLE posts (
        id INT PRIMARY KEY IDENTITY(1,1),
        slug NVARCHAR(200) UNIQUE NOT NULL,
        title NVARCHAR(200) NOT NULL,
        excerpt NVARCHAR(500),
        content NVARCHAR(MAX) NOT NULL,
        cover_image_url NVARCHAR(500),
        category_id INT REFERENCES categories(id),
        is_published BIT DEFAULT 1,
        published_at DATETIME,
        created_at DATETIME DEFAULT GETDATE(),
        updated_at DATETIME DEFAULT GETDATE()
    );
END
GO

-- ============================================================
-- 6. 商品
-- ============================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'products')
BEGIN
    CREATE TABLE products (
        id INT PRIMARY KEY IDENTITY(1,1),
        slug NVARCHAR(200) UNIQUE NOT NULL,
        name NVARCHAR(200) NOT NULL,
        description NVARCHAR(MAX),
        price DECIMAL(10, 2) NOT NULL,
        stock INT DEFAULT 0,
        image_url NVARCHAR(500),
        category_id INT REFERENCES product_categories(id),
        is_active BIT DEFAULT 1,
        created_at DATETIME DEFAULT GETDATE(),
        updated_at DATETIME DEFAULT GETDATE()
    );
END
GO

-- ============================================================
-- 7. 文章 ↔ 標籤
-- ============================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'post_tags')
BEGIN
    CREATE TABLE post_tags (
        post_id INT REFERENCES posts(id) ON DELETE CASCADE,
        tag_id INT REFERENCES tags(id),
        PRIMARY KEY (post_id, tag_id)
    );
END
GO

-- ============================================================
-- 8. 文章 ↔ 推薦商品(多對多)
-- ============================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'post_products')
BEGIN
    CREATE TABLE post_products (
        post_id INT REFERENCES posts(id) ON DELETE CASCADE,
        product_id INT REFERENCES products(id),
        sort_order INT DEFAULT 0,
        PRIMARY KEY (post_id, product_id)
    );
END
GO

-- ============================================================
-- 9. 訂單
-- ============================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'orders')
BEGIN
    CREATE TABLE orders (
        id INT PRIMARY KEY IDENTITY(1,1),
        order_number NVARCHAR(40) UNIQUE NOT NULL,
        member_id INT REFERENCES members(id),
        product_id INT REFERENCES products(id),
        quantity INT NOT NULL,
        total_price DECIMAL(10, 2) NOT NULL,
        status NVARCHAR(20) DEFAULT 'pending',
        recipient_name NVARCHAR(100),
        recipient_phone NVARCHAR(30),
        shipping_address NVARCHAR(500),
        note NVARCHAR(500),
        created_at DATETIME DEFAULT GETDATE(),
        updated_at DATETIME DEFAULT GETDATE()
    );
END
GO

-- ============================================================
-- 種子資料:文章分類
-- ============================================================
IF NOT EXISTS (SELECT * FROM categories)
BEGIN
    SET IDENTITY_INSERT categories ON;
    INSERT INTO categories (id, slug, name, description) VALUES
        (1, 'travel',  N'旅行筆記',   N'國內外慢旅行、城市散步、短途路線'),
        (2, 'reading', N'閱讀生活',   N'書單、讀書筆記、編輯室選書'),
        (3, 'daily',   N'日常選品',   N'居家、餐桌、咖啡茶、工作室日常'),
        (4, 'studio',  N'工作室日記', N'選品故事、進貨紀錄、品牌幕後');
    SET IDENTITY_INSERT categories OFF;
END
GO

-- ============================================================
-- 種子資料:商品分類
-- ============================================================
IF NOT EXISTS (SELECT * FROM product_categories)
BEGIN
    SET IDENTITY_INSERT product_categories ON;
    INSERT INTO product_categories (id, slug, name, description, sort_order) VALUES
        (1, 'reading-goods',     N'閱讀周邊',   N'書籤、筆記本、閱讀小工具',     1),
        (2, 'tableware-tea',     N'餐桌茶咖',   N'杯組、茶葉、咖啡、橄欖油',     2),
        (3, 'travel-accessories', N'旅物配件',   N'旅行收納、配件、隨身好物',     3);
    SET IDENTITY_INSERT product_categories OFF;
END
GO

-- ============================================================
-- 種子資料:標籤(id 順序固定,後面 post_tags 會用到)
-- ============================================================
IF NOT EXISTS (SELECT * FROM tags)
BEGIN
    SET IDENTITY_INSERT tags ON;
    INSERT INTO tags (id, name) VALUES
        (1,  N'taipei'),
        (2,  N'kyoto'),
        (3,  N'lisbon'),
        (4,  N'iceland'),
        (5,  N'portugal'),
        (6,  N'coffee'),
        (7,  N'tea'),
        (8,  N'books'),
        (9,  N'design'),
        (10, N'walk'),
        (11, N'handcraft'),
        (12, N'spring'),
        (13, N'summer-evening'),
        (14, N'year-end'),
        (15, N'slow'),
        (16, N'healing'),
        (17, N'inspiration');
    SET IDENTITY_INSERT tags OFF;
END
GO

-- ============================================================
-- 種子資料:會員
-- 密碼 hash 為 placeholder,未串接 auth 之前僅作示意
-- ============================================================
IF NOT EXISTS (SELECT * FROM members)
BEGIN
    SET IDENTITY_INSERT members ON;
    INSERT INTO members (id, username, email, display_name, password_hash) VALUES
        (1, N'demo',  N'demo@example.com',  N'示範會員', N'!placeholder:demo'),
        (2, N'alice', N'alice@example.com', N'Alice',    N'!placeholder:alice');
    SET IDENTITY_INSERT members OFF;
END
GO

-- ============================================================
-- 10. 管理員(站台後台用,跟一般會員分開)
-- ============================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'admins')
BEGIN
    CREATE TABLE admins (
        id INT PRIMARY KEY IDENTITY(1,1),
        username NVARCHAR(100) NOT NULL UNIQUE,
        email NVARCHAR(200) NOT NULL UNIQUE,
        display_name NVARCHAR(100),
        password_hash NVARCHAR(255) NOT NULL,
        role NVARCHAR(20) NOT NULL DEFAULT 'admin',  -- 'superadmin' / 'admin' / 'editor'
        is_active BIT DEFAULT 1,
        last_login_at DATETIME,
        failed_login_count INT DEFAULT 0,
        locked_until DATETIME,
        created_at DATETIME DEFAULT GETDATE(),
        updated_at DATETIME DEFAULT GETDATE()
    );
END
GO

-- ============================================================
-- 種子資料:預設超級管理員
-- 帳號: admin / 密碼: admin123(登入後請立刻改!)
-- hash 是 werkzeug pbkdf2:sha256 600000 算出來的
-- ============================================================
IF NOT EXISTS (SELECT * FROM admins)
BEGIN
    SET IDENTITY_INSERT admins ON;
    INSERT INTO admins (id, username, email, display_name, password_hash, role) VALUES
        (1,
         N'admin',
         N'admin@example.com',
         N'站台管理員',
         N'pbkdf2:sha256:600000$YQ61gJlWbY21Misc$351aca6891887842b3e64c41ce24f029cd8e5703408a7c51256720f50b4c9d0e',
         N'superadmin');
    SET IDENTITY_INSERT admins OFF;
END
GO

-- ============================================================
-- 種子資料:文章(8 篇)
-- ============================================================
IF NOT EXISTS (SELECT * FROM posts)
BEGIN
    SET IDENTITY_INSERT posts ON;

    -- 1. 京都三條散步
    INSERT INTO posts (id, slug, title, excerpt, content, category_id, is_published, published_at) VALUES
    (1,
     N'kyoto-sanjou-afternoon',
     N'京都三條散步:在町家咖啡店讀完一本書的午後',
     N'三條通不是京都最熱鬧的街,但如果你願意放慢,它可能是最耐逛的一條。一個下午,一杯咖啡,半本書。',
     N'三條通不是京都最熱鬧的街,但如果你願意放慢,它可能是最耐逛的一條。

沿著鴨川往南走,經過幾間町家改建的選物店、空地變身的咖啡攤,你會在某個轉角看到一扇木門,門上只寫著兩個字——喫茶。

推開門,是一百多年前的老屋子。吧台後的老闆娘不說話,只把剛煮好的咖啡放在你面前,然後回到她的位置繼續讀她自己的書。這裡沒有 wifi、沒有電源,但那個下午,我把《緩慢的歸鄉》讀完了一大半。

或許是光線對了——午後的陽光從紙窗透進來,落在杯子上,落在書頁上。也或許是時間對了——一個人出門旅行,沒有人催,沒有下一個景點,只有手裡這本書和耳邊偶爾傳來的電鈴聲。

窗外的町家、屋內的木桌、手裡的有田燒——三個時間切片在同一個空間裡疊在一起。我想起小時候外婆家也是這樣的光線,那時我還不知道「質感」兩個字怎麼寫,但已經懂得什麼叫做舒服。

如果你也計畫去京都,別急著打卡。把一整個下午留給三條,找一間讓你不想拍照的店,點一杯你叫不出名字的咖啡。然後,讓時間自己決定你要不要離開。

——
本日選品:有田燒手工對杯 / 京都丸久小山園薄茶粉',
     1, 1, '2025-03-15 10:00:00');

    -- 2. 閱讀清單
    INSERT INTO posts (id, slug, title, excerpt, content, category_id, is_published, published_at) VALUES
    (2,
     N'reading-list-2025-h1',
     N'我的極簡閱讀清單:2025 上半年最值得推薦的 5 本書',
     N'2025 才過了一半,我已經讀了 23 本書。其中有 5 本我反覆回去翻,放在床頭、放進背包,出門旅行也帶著。',
     N'2025 才過了一半,我已經讀了 23 本書。其中有些很快翻完就忘了,但有 5 本我反覆回去翻,放在床頭、放進背包,甚至出門旅行也帶著。它們不是最新、最熱門、最被推薦的書,但它們在某個晚上、某個早晨剛好接住了我。

《緩慢的歸鄉》——Peter Handke 的散文集。如果你也覺得現代生活太快、太吵、太滿,這本書像一條棉被,輕輕蓋在你身上。

《山之四季》——高村光太郎的山居筆記。一本可以隨手翻開、讀三頁就合上的書。每次合上,世界都安靜一點。

《東京八平米》——吉井忍的極簡生活實驗。一個人、八平米、沒有電視沒有冰箱,她怎麼活?讀完我開始認真想:我真的需要這麼多東西嗎?

《第一人稱單數》——村上春樹的短篇集。每篇都像一首小詩,適合睡前讀一篇。

《在咖啡館裡相遇》——Antoine Compagnon。這本書讓我重新理解「咖啡館」這件事——它不是裝飾品,是一種生活方式,也是歐洲文化的重要拼圖。

讀書這件事,從來不是讀越多越好。找到對的 5 本,讀 10 年,比追著排行榜跑更值得。

——
本日選品:黃銅鏤空書籤 / 法國再生紙筆記本',
     2, 1, '2025-04-02 09:30:00');

    -- 3. 北投天母散步
    INSERT INTO posts (id, slug, title, excerpt, content, category_id, is_published, published_at) VALUES
    (3,
     N'beitou-tianmu-walk',
     N'從北投到天母:一條適合獨自散步的小旅行路線',
     N'如果你住台北,想找一條不需要開車、不需要人陪、不需要目的地的散步路線,推薦試試北投到天母這一段。',
     N'如果你住台北,想找一條不需要開車、不需要人陪、不需要目的地的散步路線,推薦你試試北投到天母這一段。

從新北投捷運站出發,先往北投公園走,經過北投圖書館(那棟全木造的房子,每次經過我都想進去坐一下),繞過地熱谷,從北投文物館旁的小路切上去。

這段上坡是今天最累的。過了中山路,路邊開始出現日式老房子、零星的小咖啡店、幾家賣手工麵包的鋪子。你不用趕時間,看到喜歡的就停下來,點一杯,坐 20 分鐘。

繼續往天母方向走,經過美國學校旁邊的住宅區,路寬了,樹也高了。這個時候已經走了大概 1.5 小時,可以在忠誠路找間小店吃點東西——我個人推薦一家賣飯糰的老店,只開早上到下午兩點,賣完就收。

整段路大概 5–6 公里,走走停停 3–4 小時剛好。不趕路、不趕時間、不趕下一站。這才是散步。

——
本日選品:北歐羊毛氈杯墊',
     1, 1, '2025-04-22 15:00:00');

    -- 4. 馬克杯原則
    INSERT INTO posts (id, slug, title, excerpt, content, category_id, is_published, published_at) VALUES
    (4,
     N'choose-a-mug',
     N'挑一只馬克杯的 5 個原則',
     N'馬克杯是每天拿在手上的東西,選錯了,一天三次都在提醒你。下面這 5 個原則,是我這幾年換了 20 幾只杯子的心得。',
     N'馬克杯是每天拿在手上的東西,選錯了,一天三次都在提醒你。下面這 5 個原則,是我這幾年換了 20 幾只杯子的心得。

1. 容量落在 220–280ml
太大裝不滿、看起來空,太小兩口就見底。250ml 是甜蜜點。

2. 杯口厚度不要超過 4mm
厚杯口喝起來像在用碗喝茶。薄的杯口讓液體剛好落在下唇,這才是「喝」這件事的正確姿勢。

3. 把手要能伸進四指
很多人忽略把手。市售標準杯把手對男生手指頭偏小,握久了會痠。實際拿一下再決定。

4. 顏色請選「能放進博物館」的
素色、霧面、土色系,放 10 年都好看。大色塊、漸層、可愛插畫,第二年就膩了。

5. 重量不要超過 350g(含杯)
早上單手拿杯子、另一手要開冰箱的時候,你就知道我在說什麼。

按這五個原則挑下來,我家最後留下的是佐賀有田燒的對杯組,用了 3 年還在。

——
本日選品:有田燒手工對杯 / 葡萄牙軟木杯墊組',
     3, 1, '2025-05-10 11:00:00');

    -- 5. 冰島冬天
    INSERT INTO posts (id, slug, title, excerpt, content, category_id, is_published, published_at) VALUES
    (5,
     N'iceland-winter-7days',
     N'冰島冬天 7 天:那些無法拍進照片的感受',
     N'冰島冬天是另一個國家。不是風景變了,而是你跟風景的距離變了。風、黑暗、溫泉、孤獨,每一個都進到皮膚裡。',
     N'冰島冬天是另一個國家。不是風景變了,而是你跟風景的距離變了。風、黑暗、溫泉、孤獨,每一個都進到皮膚裡。

雷克雅維克的一月,下午兩點太陽就下山了。第一天我有點慌,想找地方吃飯、找地方買東西、找地方待著。後來發現當地人只是回家、看書、泡溫泉、跟家人待在一起。

我租了一台小車往南開。路面結冰,能見度不到 50 公尺,開了 20 分鐘只能停路邊等暴風雪過去。那個等待的時間,什麼都不能做,我只能坐在車裡聽風,看擋風玻璃上的冰一層一層堆。

第七天我到了一個叫 Vík 的小鎮。海邊的黑色沙灘,浪打到岩石上,飛起來的水花結冰了。我站在那邊 30 分鐘,沒有拍任何一張照片——因為拍不下來。風的形狀、冰的厚度、光線的顏色,都不是手機能收進去的。

回台灣之後,我把那段旅行放在心裡最深的地方。沒有 po 任何一張照片,但我買了條冰島設計師做的羊毛圍巾。每次圍上,冰島的風就回來一次。

——
本日選品:冰島設計師羊毛圍巾(限量 3 條)',
     1, 1, '2025-05-28 18:00:00');

    -- 6. 編輯室選書
    INSERT INTO posts (id, slug, title, excerpt, content, category_id, is_published, published_at) VALUES
    (6,
     N'march-editor-picks',
     N'編輯室選書:三月讀到一半捨不得放下的書',
     N'有些書讀完會放下,有些書讀到一半就不想放下——怕讀完就沒了。三月這 3 本,就是後者。',
     N'有些書讀完會放下,有些書讀到一半就不想放下——怕讀完就沒了。三月這 3 本,就是後者。

《在輪渡上的旅行》
船從一個島到另一個島,書從一段生活到另一段生活。作者用很輕的筆寫很重的事,讀到一半我懷疑自己到底是在船上還是在書桌前。

《植物的記憶》
植物學家的童年回憶錄,但你不需要懂植物也讀得進去。她寫外婆家的玉蘭花、寫田裡的稻穗、寫颱風夜的樹——每一段都在提醒我:忘了多久沒好好看一棵樹了。

《沒有的房間》
一個建築師的空間哲學。書很厚,但可以從任何一頁開始讀。每讀一篇,你會重新想一遍「我家的房間是給誰住的」。

三月快要結束了,如果你這個月只讀得完一本書,選《植物的記憶》。選完之後,你會想走出去,找一棵樹,看 10 分鐘。

——
本日選品:黃銅鏤空書籤 / 法國再生紙筆記本',
     2, 1, '2025-06-12 08:00:00');

    -- 7. 週末下廚
    INSERT INTO posts (id, slug, title, excerpt, content, category_id, is_published, published_at) VALUES
    (7,
     N'weekend-one-pot',
     N'週末下廚:一鍋料理的安靜時光',
     N'週末不想出門、不想見人、什麼都不想做的時候,我會煮一鍋東西。不是為了好吃,是為了那個過程。',
     N'週末不想出門、不想見人、什麼都不想做的時候,我會煮一鍋東西。不是為了好吃,是為了那個過程。

把洋蔥切丁,下鍋,聽嘶嘶聲。
把蒜頭拍扁,丟進去,聞到香味。
把番茄切塊,丟進去,顏色從白變紅。
倒進雞高湯,小火,蓋鍋,等 30 分鐘。

這 30 分鐘我可以站在廚房,什麼都不做,看鍋裡的氣泡慢慢變小。也可以坐到沙發上,聽鍋蓋被蒸氣頂得輕輕響。

一鍋料理的好處是:煮的時候不用一直顧、吃的時候不用一直想、收的時候只要洗一個鍋。

今天煮的是番茄蔬菜湯,加了從京都帶回來的丸久小山園薄茶粉做成的青醬,加一匙進去,顏色變綠,味道變深。配一片烤到焦的酸種麵包,再倒一杯和束茶。

一個下午,一鍋湯,一個人。安靜,但不是寂寞。

——
本日選品:京都和束茶 / 葡萄牙百年莊園橄欖油',
     3, 1, '2025-06-25 16:00:00');

    -- 8. 里斯本 Fado
    INSERT INTO posts (id, slug, title, excerpt, content, category_id, is_published, published_at) VALUES
    (8,
     N'lisbon-fado-evening',
     N'里斯本的傍晚:在小酒館聽 Fado 的三小時',
     N'里斯本是個黃色的城市,傍晚會更黃。我誤打誤撞走進一間 Fado 酒館,本來只想點一杯酒,結果坐到打烊。',
     N'里斯本是個黃色的城市,傍晚會更黃。我誤打誤撞走進一間 Fado 酒館,本來只想點一杯酒,結果坐到打烊。

酒館在 Alfama 區的小巷裡,門口只掛一盞昏黃的燈。推門進去,只有 6 張桌子、1 個女歌手、1 個吉他手。牆上貼滿了老照片。

我點了杯 vinho verde(綠酒),當地最便宜的白酒,等歌手開口。

Fado 是葡萄牙的「命運之歌」,歌詞聽不懂,但旋律會直接打進你胸口。歌手唱的時候眼睛不看你,看著桌上的一杯酒,像在跟那杯酒對話。

三小時裡她唱了 11 首歌,中間只喝了兩口水,沒有任何一句話語夾在中間。台下的人也安靜,連酒杯碰撞的聲音都很少。

走出酒館已經晚上 11 點,里斯本的老城街燈一盞一盞亮著,空氣裡還殘留一點歌聲。我突然明白,有些旅行,你去之前以為是去看風景,回來才發現是去聽一首歌。

——
本日選品:限量帆布旅行收納袋 / 葡萄牙百年莊園橄欖油',
     1, 1, '2025-07-08 20:00:00');

    SET IDENTITY_INSERT posts OFF;
END
GO

-- ============================================================
-- 種子資料:商品(10 件)
-- category_id:1=閱讀周邊,2=餐桌茶咖,3=旅物配件
-- ============================================================
IF NOT EXISTS (SELECT * FROM products)
BEGIN
    SET IDENTITY_INSERT products ON;
    INSERT INTO products (id, slug, name, description, price, stock, category_id) VALUES
    (1,
     N'arita-coffee-cup-set',
     N'有田燒 手工咖啡對杯(兩入組)',
     N'佐賀有田燒,400 年傳統技法。手繪釉下彩,杯壁薄透,杯型服貼手指。隨盒附原廠木箱,適合作為送禮。容量 230ml / 入。',
     1280.00, 5, 2),

    (2,
     N'brass-bookmark-trio',
     N'黃銅鏤空書籤(三件組)',
     N'京都金工作坊出品,黃銅材質,使用越久色澤越溫潤。三款造型:圓月、半月、窗花。刀口圓角處理,不傷書頁。',
     380.00, 50, 1),

    (3,
     N'portugal-olive-oil-500ml',
     N'葡萄牙百年莊園冷壓橄欖油 500ml',
     N'Trás-os-Montes 產區,莊園百年 Cobrançosa 樹種,人工採收,24 小時內冷壓。帶有青草、朝鮮薊、番茄葉的香氣。',
     780.00, 12, 2),

    (4,
     N'kyoto-matcha-40g',
     N'京都丸久小山園 薄茶粉 40g',
     N'宇治丸久小山園,薄茶等級。茶園位於京都和束町,海拔 300m,石臼研磨。適合作為日常抹茶拿鐵、烘焙、或直接點茶。',
     650.00, 20, 2),

    (5,
     N'nordic-felt-coaster-2pack',
     N'北歐羊毛氈杯墊(兩入)',
     N'立陶宛手作品牌,100% 紐西蘭羊毛,濕氈成型工法。厚度 5mm,吸水性佳,顏色為天然未染色米白與燕麥色。',
     580.00, 30, 1),

    (6,
     N'iceland-wool-scarf',
     N'冰島設計師羊毛圍巾(限量)',
     N'冰島設計師 Brynjar 工作室出品,使用冰島特有 Lopapeysa 雙層編織技法。100% Icelandic wool,長 200cm / 寬 30cm,男女皆宜。限量 3 條。',
     2680.00, 3, 3),

    (7,
     N'france-recycled-notebook-a5',
     N'法國再生紙手工筆記本 A5',
     N'Clairefontaine 再生紙,80gsm 米白色紙張,書寫滑順不暈墨。線裝,可 180 度攤平。封面為厚磅灰色美術紙。144 頁。',
     420.00, 100, 1),

    (8,
     N'portugal-cork-coaster-4pack',
     N'葡萄牙軟木杯墊組(四入)',
     N'阿連特茹產區軟木,採集後需靜置 9 個月才能加工。直徑 10cm,厚度 8mm,背面有防滑襯墊。隨盒附麻布收納袋。',
     460.00, 25, 1),

    (9,
     N'kyoto-wazuka-tea-100g',
     N'京都和束茶 100g 罐裝',
     N'和束町位於京都府南丹山區,被譽為「茶的故鄉」。本款為煎茶與焙茶 1:1 調和,日常飲用、口感溫潤不苦澀。',
     520.00, 18, 2),

    (10,
     N'canvas-travel-pouch',
     N'限量帆布旅行收納袋',
     N'日本岡山倉敷帆布,6 號帆厚度,附皮革提把與銅扣。內側有 3 個夾層,可分類放置盥洗、保養、文具小物。尺寸 25 x 18 x 12 cm。',
     880.00, 15, 3);

    SET IDENTITY_INSERT products OFF;
END
GO

-- ============================================================
-- 種子資料:文章 ↔ 標籤
-- (post_id, tag_id) — 對應上述 8 篇文章與 17 個 tag 的 id
-- ============================================================
IF NOT EXISTS (SELECT * FROM post_tags)
BEGIN
    INSERT INTO post_tags (post_id, tag_id) VALUES
        (1, 2),  (1, 6),  (1, 15),    -- post1: kyoto, coffee, slow
        (2, 8),                       -- post2: books
        (3, 1),  (3, 10),             -- post3: taipei, walk
        (4, 6),  (4, 9),              -- post4: coffee, design
        (5, 4),  (5, 16),             -- post5: iceland, healing
        (6, 8),  (6, 12),             -- post6: books, spring
        (7, 15),                      -- post7: slow
        (8, 3),  (8, 17);             -- post8: lisbon, inspiration
END
GO

-- ============================================================
-- 種子資料:文章 ↔ 推薦商品
-- ============================================================
IF NOT EXISTS (SELECT * FROM post_products)
BEGIN
    INSERT INTO post_products (post_id, product_id, sort_order) VALUES
        (1, 1, 1), (1, 4, 2),   -- post1: arita cup, matcha
        (2, 2, 1), (2, 7, 2),   -- post2: bookmark, notebook
        (3, 5, 1),              -- post3: felt coaster
        (4, 1, 1), (4, 8, 2),   -- post4: arita cup, cork coaster
        (5, 6, 1),              -- post5: iceland scarf
        (6, 2, 1), (6, 7, 2),   -- post6: bookmark, notebook
        (7, 9, 1), (7, 3, 2),   -- post7: wazuka tea, olive oil
        (8, 10, 1), (8, 3, 2);  -- post8: canvas pouch, olive oil
END
GO

-- ============================================================
-- 種子資料:訂單(2 筆示意)
-- ============================================================
IF NOT EXISTS (SELECT * FROM orders)
BEGIN
    SET IDENTITY_INSERT orders ON;
    INSERT INTO orders (id, order_number, member_id, product_id, quantity, total_price, status,
                        recipient_name, recipient_phone, shipping_address, note) VALUES
    (1,
     N'ORD-2025-0001',
     1, 1, 1, 1280.00, N'paid',
     N'王小明', N'0912-345-678',
     N'台北市大安區辛亥路二段 17 號 3 樓',
     N'平日送達,謝謝'),

    (2,
     N'ORD-2025-0002',
     2, 7, 2, 840.00, N'pending',
     N'Alice Chen', N'0923-456-789',
     N'新北市永和區中山路一段 88 號 5 樓',
     NULL);

    SET IDENTITY_INSERT orders OFF;
END
GO

PRINT '資料庫初始化完成';
GO
