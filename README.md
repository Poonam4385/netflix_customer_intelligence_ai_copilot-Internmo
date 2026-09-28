# Netflix Customer Intelligence & AI Analytics Copilot

An advanced end-to-end **Data Science + Analytics Engineering + Generative AI** portfolio project modeled on a streaming subscription business. The data are synthetic and are **not Netflix production/customer data**.

## What this project demonstrates

- PostgreSQL analytics engineering over 9 related tables and ~200k transactional/event records.
- Data quality remediation, payment-to-subscription reconciliation, and auditable cleaning.
- Leakage-aware customer feature engineering.
- Churn classification with Logistic Regression, Random Forest, and XGBoost.
- K-Means customer segmentation with silhouette-based K selection and business cluster naming.
- Customer Lifetime Value regression with Ridge, Random Forest, and XGBoost.
- SHAP/local feature explanations for churn predictions.
- Secured Text-to-SQL with schema validation, read-only enforcement, row caps, timeout, and audit logs.
- RAG over support tickets and customer feedback using embeddings + FAISS.
- Automated executive reports, root-cause analysis, and rules-plus-LLM retention recommendations.
- Seven-view Streamlit application.
- Docker packaging, tests, reproducible bootstrap scripts, and notebooks.

## Attachment-specific findings already handled

The supplied data intentionally contain quality problems. The cleaning pipeline currently detects/resolves:

- 48 duplicate `customer_id` rows in customers, reducing 8,048 raw rows to 8,000 unique customers.
- 21 implausible ages outside 13–100, imputed after validation.
- 83 raw country spellings/codes normalized into canonical country names.
- 23 raw device labels normalized into a canonical device set.
- 61 invalid support-ticket dates converted to null while retaining the ticket text and metadata.
- 263 feedback rows where the supplied sentiment label disagrees with a simple rating-based sentiment rule; the original label is retained for auditability.
- 570 historical `Plan Changed` subscription rows where `plan_id` and stored `monthly_price` differ; these are retained rather than silently overwritten because they reflect transition-history semantics in the supplied synthetic data.
- Every `payments.subscription_id` is blank in the raw file. The pipeline first interval-matches payments to the active subscription segment and then links post-cancellation synthetic billing rows to the most recent prior subscription, leaving **0 unresolved payment subscription IDs**.

The feature pipeline anchors churned customers at their churn date and non-churned customers at the latest observed event date (2026-06-30), preventing post-churn viewing/support/payment activity from entering the churn predictors.

## Validated model baseline on the supplied files

A fast validation run produced:

- Churn: XGBoost selected; test ROC-AUC about **0.812** and average precision about **0.674**. The supplied retention threshold is optimized for F2, intentionally favoring recall for retention targeting.
- CLV: XGBoost selected; test **R² about 0.904**, RMSE about **31.7**, MAE about **12.1**.
- Segmentation: silhouette evaluation over K=2..7 selected **K=7** in the current run.

Re-run the full pipeline locally to regenerate final metrics from your environment.

---

# 1. Project structure

```text
netflix_customer_intelligence_ai_copilot/
├── data/
│   ├── raw/                       # normalized names for the 9 supplied CSVs
│   └── processed/                 # cleaned facts + customer feature/score marts
├── database/
│   ├── schema.sql
│   ├── analytics_views.sql
│   ├── business_queries.sql       # all 37 required SQL analyses
│   └── load_data.py
├── notebooks/
│   ├── 01_data_cleaning.ipynb
│   ├── 02_exploratory_analysis.ipynb  # 25 visualization cells
│   ├── 03_feature_engineering.ipynb
│   ├── 04_churn_prediction.ipynb
│   ├── 05_customer_segmentation.ipynb
│   └── 06_clv_prediction.ipynb
├── src/
│   ├── data_processing/clean_data.py
│   ├── features/build_features.py
│   ├── models/
│   ├── database/
│   ├── llm/                       # OpenAI/Ollama client, Text-to-SQL, RAG
│   ├── services/                  # explanations, retention, reports, root cause
│   └── utils/
├── app/
│   ├── dashboard.py               # Executive dashboard
│   └── pages/                     # six additional Streamlit pages
├── models/
├── reports/
├── tests/
├── scripts/bootstrap.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

# 2. Environment setup

Python 3.10+ is supported; Python 3.11 is a good default.

### Windows PowerShell

```powershell
cd "D:\Poonam Docs\ML Projects\netflix_customer_intelligence_ai_copilot"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

### macOS/Linux

```bash
cd netflix_customer_intelligence_ai_copilot
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

# 3. Configure `.env`

For PostgreSQL:

```env
DATABASE_URL=postgresql+psycopg2://netflix:netflix@localhost:5432/netflix_ci
```

For hosted LLM generation:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5.6-luna
RAG_EMBEDDING_PROVIDER=local
```

Or use Ollama for text generation:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
```

The default RAG embedding backend is a local SentenceTransformer. Set `RAG_EMBEDDING_PROVIDER=openai` if you prefer hosted embeddings.

# 4. Run cleaning only

```bash
python -m src.data_processing.clean_data
```

Outputs cleaned versions of all 9 tables plus:

```text
data/processed/cleaning_report.json
```

# 5. Build the customer feature mart

```bash
python -m src.features.build_features
```

The result is:

```text
data/processed/customer_features.csv
```

Important engineered features include:

- `customer_tenure_days`
- `avg_watch_time_per_session`
- `monthly_watch_time_trend`
- `days_since_last_activity`
- `login_frequency`
- `support_ticket_count`
- `avg_customer_satisfaction`
- `failed_payment_count`
- `failed_payment_rate`
- `plan_changes`
- `engagement_score`
- `customer_lifetime_value`
- plus 30-day watch change, 90-day device/genre diversity, failed-payment recency, low-CSAT rate, negative-feedback rate, billing-risk score, and support-friction score.

# 6. Train the three required ML models

### Churn

```bash
python -m src.models.train_churn
```

For a faster development run:

```bash
python -m src.models.train_churn --fast
```

The script:

1. excludes direct outcome-leakage columns,
2. imputes numeric/categorical values,
3. one-hot encodes categoricals,
4. compares Logistic Regression, Random Forest, and XGBoost with stratified CV,
5. selects the strongest CV ROC-AUC model,
6. generates out-of-fold probabilities,
7. tunes an F2 threshold for retention use,
8. evaluates Accuracy, Precision, Recall, F1, F2, ROC-AUC, Average Precision, and confusion matrix,
9. serializes the final pipeline,
10. scores every customer into Low/Medium/High/Critical bands.

### Segmentation

```bash
python -m src.models.train_segmentation
```

This evaluates K=2..7 using silhouette score and generates cluster profiles and PCA coordinates.

### CLV

```bash
python -m src.models.train_clv
```

Direct target proxies such as successful-payment count are excluded from predictors so the regression does not trivially reconstruct lifetime value.

# 7. One-command local ML bootstrap

```bash
python scripts/bootstrap.py --fast
```

Full model configuration:

```bash
python scripts/bootstrap.py
```

Add `--rag` to also build the FAISS support/feedback index.

# 8. PostgreSQL setup

The easiest approach is Docker:

```bash
docker compose up -d db
```

Then load the cleaned data:

```bash
python database/load_data.py
python scripts/run_sql_views.py
```

The project includes all **37 SQL business questions** in:

```text
database/business_queries.sql
```

They cover joins/aggregations, window functions, moving averages, cohorts, CLV quartiles, plan migration, churn, WAU/MAU stickiness, proactive retention, at-risk revenue, and customer health scoring.

# 9. Build the RAG index

```bash
python -m src.llm.rag
```

It embeds:

- `support_tickets.ticket_description`
- `customer_feedback.feedback_text`

and writes a FAISS index plus JSONL metadata under `models/`.

Every generated answer is grounded in retrieved records and instructed to cite ticket/feedback IDs.

# 10. Text-to-SQL security design

`src/llm/text_to_sql.py` implements:

- only one statement,
- SELECT/CTE only,
- blocking of INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/MERGE/commands,
- referenced-table validation against live database schema,
- qualified-column checks,
- PostgreSQL statement timeout,
- maximum returned row count,
- audit log of question, SQL, status, row count, elapsed time, and error.

Never execute arbitrary model-generated SQL without this validation layer.

# 11. Prediction explanation

`src/services/prediction_explainer.py` loads the trained churn model and produces:

- churn probability,
- retention threshold,
- top local SHAP/model contributions,
- human-readable business feature values,
- optional LLM explanation constrained to the supplied model evidence.

# 12. Retention recommendation engine

`src/services/retention.py` combines:

- churn probability/risk percentile,
- CLV percentile,
- customer cluster,
- engagement,
- payment reliability,
- support satisfaction,

into a deterministic action policy first. The LLM only phrases/explains the recommendation; it is not allowed to invent customer facts.

# 13. Automated reports and root-cause agent

`src/services/reports.py` retrieves calculated revenue, churn, customer growth, engagement, CSAT, and complaint metrics, then asks the LLM to write an executive narrative without changing any numbers.

`src/services/root_cause.py` follows a fixed diagnostic sequence for a country/month:

1. churn movement,
2. engagement movement,
3. payment-failure movement,
4. support/CSAT movement,
5. plan mix,
6. evidence-weighted interpretation.

This is safer and more auditable than giving an LLM unrestricted database access.

# 14. Run Streamlit

```bash
streamlit run app/dashboard.py
```

The seven application views are:

1. Executive Dashboard
2. Customer Analytics
3. Churn Prediction & Explainability
4. Customer Segmentation
5. AI Analytics Copilot
6. Support Intelligence
7. Automated Reports & Root-Cause Analysis

# 15. Run tests

```bash
pytest -q
```

# 16. Full Docker deployment

Create `.env`, then:

```bash
docker compose up --build
```

Open Streamlit at `http://localhost:8501`.

Before using Text-to-SQL/reporting inside Docker, load the database once from the app container or host environment.

# 17. Recommended project execution order

Use this exact sequence for a clean portfolio build:

```text
1. 01_data_cleaning.ipynb
2. Load PostgreSQL schema + cleaned data
3. Solve/review the 37 SQL questions
4. 02_exploratory_analysis.ipynb
5. 03_feature_engineering.ipynb
6. 04_churn_prediction.ipynb
7. 05_customer_segmentation.ipynb
8. 06_clv_prediction.ipynb
9. Build RAG index
10. Test Text-to-SQL validation
11. Test SHAP prediction explanation
12. Generate retention priorities
13. Generate an automated report
14. Run a root-cause investigation
15. Launch and test all Streamlit pages
16. Run pytest
17. Dockerize and publish the repository
```

# 18. Portfolio positioning

**GitHub title**  
`netflix-customer-intelligence-ai-copilot`

**One-line summary**  
Built an end-to-end customer intelligence platform modeled on a streaming subscription business, combining PostgreSQL analytics, churn/segmentation/CLV machine learning, explainable AI, secured Text-to-SQL, RAG-based support intelligence, automated root-cause analysis, and an interactive Streamlit copilot.

**Important presentation wording**  
Say **“modeled on Netflix’s subscription business using synthetic data”**, not “Netflix customer data” or “built for Netflix.”
