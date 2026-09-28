import pytest
sqlglot=pytest.importorskip("sqlglot")
from src.llm.text_to_sql import validate_sql
CAT={"customers":["customer_id","country"],"payments":["customer_id","amount","payment_status"]}

def test_allows_select():
    assert validate_sql("SELECT country, COUNT(*) FROM customers GROUP BY country",CAT)

def test_blocks_delete():
    with pytest.raises(ValueError): validate_sql("DELETE FROM customers",CAT)

def test_blocks_unknown_table():
    with pytest.raises(ValueError): validate_sql("SELECT * FROM secrets",CAT)
