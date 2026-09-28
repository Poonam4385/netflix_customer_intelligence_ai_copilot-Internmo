from __future__ import annotations
import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor
from src.models.common import load_features, model_columns, make_preprocessor, MODELS, DATA, write_json

RANDOM_STATE=42

def reg_metrics(y, pred):
    return {"mae": mean_absolute_error(y,pred), "rmse": mean_squared_error(y,pred)**0.5, "r2": r2_score(y,pred)}

def main():
    df=load_features()
    target="customer_lifetime_value"
    # Exclude direct accounting proxies to avoid trivially reconstructing CLV.
    extra_drop={"successful_payment_count","payment_count_90d"}
    numeric,categorical=model_columns(df,target,extra_drop)
    features=numeric+categorical
    X=df[features]; y=df[target].astype(float)
    Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=.2,random_state=RANDOM_STATE)
    candidates={
        "ridge": Ridge(alpha=5.0),
        "random_forest": RandomForestRegressor(n_estimators=300,min_samples_leaf=3,max_features=.8,n_jobs=-1,random_state=RANDOM_STATE),
        "xgboost": XGBRegressor(n_estimators=350,max_depth=4,learning_rate=.04,subsample=.85,colsample_bytree=.85,reg_lambda=2.0,n_jobs=-1,random_state=RANDOM_STATE,objective="reg:squarederror"),
    }
    results={}; fitted={}
    for name,model in candidates.items():
        pre=make_preprocessor(numeric,categorical,scale_numeric=(name=="ridge"))
        pipe=Pipeline([("preprocess",pre),("model",model)])
        pipe.fit(Xtr,ytr)
        pred=np.clip(pipe.predict(Xte),0,None)
        results[name]=reg_metrics(yte,pred); fitted[name]=pipe
        print(name,results[name])
    best_name=min(results,key=lambda k:results[k]["rmse"])
    best=fitted[best_name]
    joblib.dump(best,MODELS/"clv_pipeline.joblib")
    write_json(MODELS/"clv_metadata.json",{"selected_model":best_name,"metrics":results,"features":features,"numeric_features":numeric,"categorical_features":categorical})
    df[["customer_id",target]].assign(predicted_clv=np.clip(best.predict(X),0,None)).to_csv(DATA/"customer_clv_predictions.csv",index=False)
    print("Selected",best_name)

if __name__=="__main__": main()
