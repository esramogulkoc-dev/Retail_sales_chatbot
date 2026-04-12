few_shots = [
    {
        "input": "How many total t-shirts are left in stock?",
        "query": "SELECT SUM(stock_quantity) FROM t_shirts;",
        "answer": "The total number of t-shirts left in stock is {result}"
    },
    {
        "input": "How many t-shirts do we have for Nike in small size?",
        "query": "SELECT stock_quantity FROM t_shirts WHERE brand='Nike' AND size='S';",
        "answer": "We have {result} Nike t-shirts in S size"
    },
    {
        "input": "What is the total price of all inventory for S-size t-shirts?",
        "query": "SELECT SUM(price * stock_quantity) FROM t_shirts WHERE color='Red';",
        "answer": "The total inventory value for red color t-shirts is {result}"
    },
    {
        "input": "How much sales will we generate if we sell all Adidas shirts?",
        "query": "SELECT SUM(t.price * (1 - d.pct_discount / 100) * t.stock_quantity) AS total_discounted_revenue FROM t_shirts t JOIN discounts d ON t.t_shirt_id = d.t_shirt_id WHERE t.brand = 'Adidas';",
        "answer": "If we sell all Adidas t-shirts, we will generate {result} in sales"
    },
    {
        "input": "How many different colors of t-shirts do we have?",
        "query": "SELECT COUNT(DISTINCT color) FROM t_shirts;",
        "answer": "We have {result} different colors of t-shirts"
    },
    {
        "input": "What is the average price of Nike t-shirts?",
        "query": "SELECT ROUND(AVG(price), 2) FROM t_shirts WHERE brand='Nike';",
        "answer": "The average price of Nike t-shirts is {result}"
    },
    {
        "input": "How many t-shirts do we have from each brand?",
        "query": "SELECT brand, SUM(stock_quantity) as total_stock FROM t_shirts GROUP BY brand ORDER BY total_stock DESC;",
        "answer": "Stock by brand: {result}"
    },
        {
            "input": "Which size has the most t-shirts in stock?",
            "query": "SELECT size FROM t_shirts GROUP BY size ORDER BY SUM(stock_quantity) DESC LIMIT 1;",
            "answer": "The size with the most t-shirts in stock is {result}"
        }
    ]