# Model Evaluation Snapshot

These metrics come from the validation run executed while assembling the project. Re-run the scripts for final portfolio metrics.

## Churn
- Selected model: xgboost
- ROC-AUC: 0.812
- Average precision: 0.674
- Retention threshold: 0.340
- Precision: 0.354
- Recall: 0.912
- F1: 0.510
- F2: 0.694

The threshold intentionally emphasizes recall because missing a genuinely high-risk customer can be more costly than reviewing some false positives. Offer economics should ultimately determine the production threshold.

## CLV
- Selected model: xgboost
- R²: 0.904
- RMSE: 31.71
- MAE: 12.09

## Segmentation
- Selected K: 7
- Best silhouette score: 0.280
