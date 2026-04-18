few_shots = [
    {
        "question": "What is the total stock quantity available for each brand, ordered from highest to lowest?",
        "SQLQuery": "SELECT brand, SUM(stock_quantity) AS total_stock FROM t_shirts GROUP BY brand ORDER BY total_stock DESC",
        "SQLResult": "Result of the SQL query",
        "answer": "[('Levi', 1128), ('Nike', 1044), ('Adidas', 1029), ('Van Huesen', 1016)]"
    },
    {
        "question": "Which brand has the highest average price per shirt, and what is that average price?",
        "SQLQuery": "SELECT brand, AVG(price) as avg_price FROM t_shirts GROUP BY brand ORDER BY avg_price DESC LIMIT 1",
        "SQLResult": "Result of the SQL query",
        "answer": "[('Nike', 33.7)]"
    },
    {
        "question": "What is the total stock per size?",
        "SQLQuery": "SELECT size, SUM(stock_quantity) AS total_stock FROM t_shirts GROUP BY size",
        "SQLResult": "Result of the SQL query",
        "answer": "[('L', 760), ('M', 806), ('S', 855), ('XL', 936), ('XS', 860)]"
    },
    {
        "question": "What is the total inventory value of all small size t-shirts?",
        "SQLQuery": "SELECT SUM(price * stock_quantity) AS total_value FROM t_shirts WHERE size = 'S'",
        "SQLResult": "Result of the SQL query",
        "answer": "26441"
    },
    {
        "question": "If we have to sell all Adidas t-shirts, what would be the total revenue with discount?",
        "SQLQuery": "SELECT SUM(t.price * (1 - d.pct_discount / 100) * t.stock_quantity) AS total_discounted_revenue FROM t_shirts t JOIN discounts d ON t.t_shirt_id = d.t_shirt_id WHERE t.brand = 'Adidas'",
        "SQLResult": "Result of the SQL query",
        "answer": "21478.59"
    },
    {
        "question": "How many white color Levi t-shirts do we have?",
        "SQLQuery": "SELECT SUM(`stock_quantity`) FROM `t_shirts` WHERE `color` = 'White' AND `brand` = 'Levi'",
        "SQLResult": "Result of the SQL query",
        "answer": "341"
    },
    {
        "question": "How many red color Adidas t-shirts do we have?",
        "SQLQuery": "SELECT SUM(`stock_quantity`) FROM `t_shirts` WHERE `brand` = 'Adidas' AND `color` = 'Red'",
        "SQLResult": "Result of the SQL query",
        "answer": "185"
    },
]
