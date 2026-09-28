import pandas as pd
from src.models.common import DATA

def test_customers_unique():
    df=pd.read_csv(DATA/"customers.csv")
    assert not df.customer_id.duplicated().any()
    assert len(df)==8000

def test_payment_subscription_resolved():
    df=pd.read_csv(DATA/"payments.csv")
    assert df.subscription_id.notna().all()

def test_churn_one_per_customer():
    df=pd.read_csv(DATA/"churn_labels.csv")
    assert len(df)==df.customer_id.nunique()==8000

def test_feature_table_complete():
    df=pd.read_csv(DATA/"customer_features.csv")
    required={"customer_id","churned","engagement_score","failed_payment_rate","customer_lifetime_value"}
    assert required.issubset(df.columns)
    assert len(df)==8000
