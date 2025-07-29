from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from database.db_manager import DatabaseManager

db_manager = DatabaseManager()


@tool
def get_available_categories() -> Dict[str, List[str]]:
    """Returns a list of available product categories."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT Category
            FROM products
            WHERE Quantity > 0
        """
        )
        categories = cursor.fetchall()
        return {"categories": [category["Category"] for category in categories]}


@tool
def search_products(
    query: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Searches for products based on various criteria.

    Arguments:
        query (Optional[str]): Search term for product name or description
        category (Optional[str]): Filter by product category
        min_price (Optional[float]): Minimum price filter
        max_price (Optional[float]): Maximum price filter

    Returns:
        Dict[str, Any]: Search results with products and metadata

    Example:
        search_products(query="banana", category="fruits", max_price=5.00)
    """
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        query_parts = ["SELECT * FROM products WHERE Quantity > 0"]
        params = []

        if query:
            query_parts.append(
                """
                AND (
                    LOWER(ProductName) LIKE ? 
                    OR LOWER(Description) LIKE ?
                )
            """
            )
            search_term = f"%{query.lower()}%"
            params.extend([search_term, search_term])

        if category:
            query_parts.append("AND LOWER(Category) = ?")
            params.append(category.lower())

        if min_price is not None:
            query_parts.append("AND Price >= ?")
            params.append(min_price)

        if max_price is not None:
            query_parts.append("AND Price <= ?")
            params.append(max_price)

        # Execute search query
        cursor.execute(" ".join(query_parts), params)
        products = cursor.fetchall()

        # Get available categories for metadata
        cursor.execute(
            """
            SELECT DISTINCT Category, COUNT(*) as count 
            FROM products 
            WHERE Quantity > 0 
            GROUP BY Category
        """
        )
        categories = cursor.fetchall()

        # Get price range for metadata
        cursor.execute(
            """
            SELECT 
                MIN(Price) as min_price,
                MAX(Price) as max_price,
                AVG(Price) as avg_price
            FROM products
            WHERE Quantity > 0
        """
        )
        price_stats = cursor.fetchone()

        return {
            "status": "success",
            "products": [
                {
                    "product_id": str(product["ProductId"]),
                    "name": product["ProductName"],
                    "category": product["Category"],
                    "description": product["Description"],
                    "price": float(product["Price"]),
                    "stock": product["Quantity"],
                }
                for product in products
            ],
            "metadata": {
                "total_results": len(products),
                "categories": [
                    {"name": cat["Category"], "product_count": cat["count"]}
                    for cat in categories
                ],
                "price_range": {
                    "min": float(price_stats["min_price"]),
                    "max": float(price_stats["max_price"]),
                    "average": round(float(price_stats["avg_price"]), 2),
                },
            },
        }


@tool
def create_order(
    products: List[Dict[str, Any]], *, config: RunnableConfig
) -> Dict[str, str]:
    """
    Creates a new order (product purchase) for the customer.

     Arguments:
         products (List[Dict[str, Any]]): The list of products to be purchased.

     Returns:
         Dict[str, str]: Order details including status and message

     Example:
         create_order([{"ProductName": "Product A", "Quantity": 2}, {"ProductName": "Product B", "Quantity": 1}])
    """
    configuration = config.get("configurable", {})
    customer_id = configuration.get("customer_id", None)

    if not customer_id:
        return ValueError("No customer ID configured.")

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        try:
            # Start transaction
            cursor.execute("BEGIN TRANSACTION")

            # Create order
            cursor.execute(
                """INSERT INTO orders (CustomerId, OrderDate, Status) 
                   VALUES (?, ?, ?)""",
                (customer_id, datetime.now().isoformat(), "Pending"),
            )
            order_id = cursor.lastrowid

            total_amount = Decimal("0")
            ordered_products = []

            # Process each product
            for item in products:
                product_name = item["ProductName"]
                quantity = item["Quantity"]

                # Get product details
                cursor.execute(
                    "SELECT ProductId, Price, Quantity FROM products WHERE LOWER(ProductName) = LOWER(?)",
                    (product_name,),
                )
                product = cursor.fetchone()

                if not product:
                    raise ValueError(f"Product not found: {product_name}")

                if product["Quantity"] < quantity:
                    raise ValueError(f"Insufficient stock for {product_name}")

                # Add order detail
                cursor.execute(
                    """INSERT INTO orders_details (OrderId, ProductId, Quantity, UnitPrice) 
                       VALUES (?, ?, ?, ?)""",
                    (order_id, product["ProductId"], quantity, product["Price"]),
                )

                # Update inventory
                cursor.execute(
                    "UPDATE products SET Quantity = Quantity - ? WHERE ProductId = ?",
                    (quantity, product["ProductId"]),
                )

                total_amount += Decimal(str(product["Price"])) * Decimal(str(quantity))
                ordered_products.append(
                    {
                        "name": product_name,
                        "quantity": quantity,
                        "unit_price": float(product["Price"]),
                    }
                )

            cursor.execute("COMMIT")

            return {
                "order_id": str(order_id),
                "status": "success",
                "message": "Order created successfully",
                "total_amount": float(total_amount),
                "products": ordered_products,
                "customer_id": str(customer_id),
            }

        except Exception as e:
            cursor.execute("ROLLBACK")
            return {
                "status": "error",
                "message": str(e),
                "customer_id": str(customer_id),
            }


@tool
def check_order_status(
    order_id: Union[str, None], *, config: RunnableConfig
) -> Dict[str, Union[str, None]]:
    """
    Checks the status of a specific order or all customer orders.

    Arguments:
        order_id (Union[str, None]): The ID of the order to check. If None, all customer orders will be returned.
    """
    configuration = config.get("configurable", {})
    customer_id = configuration.get("customer_id", None)

    if not customer_id:
        raise ValueError("No customer ID configured.")

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        if order_id:
            # Query specific order
            cursor.execute(
                """
                SELECT 
                    o.OrderId,
                    o.OrderDate,
                    o.Status,
                    GROUP_CONCAT(p.ProductName || ' (x' || od.Quantity || ')') as Products,
                    SUM(od.Quantity * od.UnitPrice) as TotalAmount
                FROM orders o
                JOIN orders_details od ON o.OrderId = od.OrderId
                JOIN products p ON od.ProductId = p.ProductId
                WHERE o.OrderId = ? AND o.CustomerId = ?
                GROUP BY o.OrderId
            """,
                (order_id, customer_id),
            )

            order = cursor.fetchone()
            if not order:
                return {
                    "status": "error",
                    "message": "Order not found",
                    "customer_id": str(customer_id),
                    "order_id": str(order_id),
                }

            return {
                "status": "success",
                "order_id": str(order["OrderId"]),
                "order_date": order["OrderDate"],
                "order_status": order["Status"],
                "products": order["Products"],
                "total_amount": float(order["TotalAmount"]),
                "customer_id": str(customer_id),
            }
        else:
            # Query all customer orders
            cursor.execute(
                """
                SELECT 
                    o.OrderId,
                    o.OrderDate,
                    o.Status,
                    COUNT(od.OrderDetailId) as ItemCount,
                    SUM(od.Quantity * od.UnitPrice) as TotalAmount
                FROM orders o
                JOIN orders_details od ON o.OrderId = od.OrderId
                WHERE o.CustomerId = ?
                GROUP BY o.OrderId
                ORDER BY o.OrderDate DESC
            """,
                (customer_id,),
            )

            orders = cursor.fetchall()
            return {
                "status": "success",
                "customer_id": str(customer_id),
                "orders": [
                    {
                        "order_id": str(order["OrderId"]),
                        "order_date": order["OrderDate"],
                        "status": order["Status"],
                        "item_count": order["ItemCount"],
                        "total_amount": float(order["TotalAmount"]),
                    }
                    for order in orders
                ],
            }


@tool
def search_products_recommendations(config: RunnableConfig) -> Dict[str, str]:
    """Searches for product recommendations for the customer."""
    configuration = config.get("configurable", {})
    customer_id = configuration.get("customer_id", None)

    if not customer_id:
        raise ValueError("No customer ID configured.")

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        # Get customer's previous purchases
        cursor.execute(
            """
            SELECT DISTINCT p.Category
            FROM orders o
            JOIN orders_details od ON o.OrderId = od.OrderId
            JOIN products p ON od.ProductId = p.ProductId
            WHERE o.CustomerId = ?
            ORDER BY o.OrderDate DESC
            LIMIT 3
        """,
            (customer_id,),
        )

        favorite_categories = cursor.fetchall()

        if not favorite_categories:
            # If no purchase history, recommend popular products
            cursor.execute(
                """
                SELECT 
                    ProductId,
                    ProductName,
                    Category,
                    Description,
                    Price,
                    Quantity
                FROM products
                WHERE Quantity > 0
                ORDER BY RANDOM()
                LIMIT 5
            """
            )
        else:
            # Recommend products from favorite categories
            placeholders = ",".join("?" * len(favorite_categories))
            categories = [cat["Category"] for cat in favorite_categories]

            cursor.execute(
                f"""
                SELECT 
                    ProductId,
                    ProductName,
                    Category,
                    Description,
                    Price,
                    Quantity
                FROM products
                WHERE Category IN ({placeholders})
                AND Quantity > 0
                ORDER BY RANDOM()
                LIMIT 5
            """,
                categories,
            )

        recommendations = cursor.fetchall()

        return {
            "status": "success",
            "customer_id": str(customer_id),
            "recommendations": [
                {
                    "product_id": str(product["ProductId"]),
                    "name": product["ProductName"],
                    "category": product["Category"],
                    "description": product["Description"],
                    "price": float(product["Price"]),
                    "stock": product["Quantity"],
                }
                for product in recommendations
            ],
        }
