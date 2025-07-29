CREATE TABLE IF NOT EXISTS products (
    ProductId INTEGER PRIMARY KEY AUTOINCREMENT,
    ProductName TEXT NOT NULL,
    Category TEXT NOT NULL,
    Description TEXT,
    Price DOUBLE NOT NULL CHECK(Price > 0),
    Quantity INTEGER NOT NULL CHECK(Quantity >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    OrderId INTEGER PRIMARY KEY AUTOINCREMENT,
    CustomerId INTEGER NOT NULL,
    OrderDate TEXT NOT NULL,
    Status TEXT NOT NULL CHECK(Status IN ('Pending', 'Shipped', 'Cancelled', 'Completed')),
    FOREIGN KEY (CustomerId) REFERENCES Customers (CustomerId)
);

CREATE TABLE IF NOT EXISTS orders_details (
    OrderDetailId INTEGER PRIMARY KEY AUTOINCREMENT,
    OrderId INTEGER NOT NULL,
    ProductId INTEGER NOT NULL,
    Quantity INTEGER NOT NULL CHECK(Quantity > 0),
    UnitPrice REAL NOT NULL CHECK(UnitPrice > 0),
    FOREIGN KEY (OrderId) REFERENCES Orders (OrderId),
    FOREIGN KEY (ProductId) REFERENCES Products (ProductId)
);