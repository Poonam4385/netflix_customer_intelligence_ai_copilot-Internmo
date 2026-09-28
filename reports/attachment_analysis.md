# Attachment Analysis — Netflix Customer Intelligence & AI Analytics Copilot

## 1. Supplied package

The uploaded ZIP contains nine synthetic datasets plus four project-specification documents:

| Dataset | Rows | Main role |
|---|---:|---|
| customers | 8,048 raw / 8,000 unique | demographics and acquisition |
| subscription_plans | 3 | plan catalog |
| subscriptions | 8,875 | subscription history / plan changes |
| content | 500 | content metadata |
| viewing_activity | 66,422 | engagement events |
| payments | 110,735 | billing and failures |
| support_tickets | 6,120 | structured + free-text support |
| customer_feedback | 5,046 | rating/sentiment/free text |
| churn_labels | 8,000 | churn target |

The accompanying PRD requires 37 SQL analyses, a minimum of 20 EDA visualizations, churn classification, K-Means segmentation, CLV regression, six GenAI copilot capabilities, and a seven-view Streamlit app.

## 2. Important data-quality findings

- `customers.customer_id` contains 48 duplicate rows.
- `state_or_region` is blank for all 8,048 raw customer rows and should not be treated as a useful model feature.
- `age` contains 21 values outside a practical 13–100 validation range; the raw minimum is 2 and maximum is 145.
- Country/location data use 83 different spellings/codes/cases before normalization.
- Device types use 23 labels before normalization.
- `completion_percentage` contains missing values.
- `support_tickets.ticket_date` contains 61 impossible date strings such as `2025-13-45`.
- Raw `payments.subscription_id` is blank for all 110,735 payment rows.
- 263 feedback records disagree with a simple rating-based sentiment interpretation; this aligns with the PRD's intentionally noisy sentiment labels.
- 570 `Plan Changed` subscription rows have a stored `monthly_price` that does not match the catalog price of the row's `plan_id`. These should be audited rather than silently overwritten because the synthetic generator appears to encode transition history in these rows.
- Some synthetic payment rows occur after the recorded cancellation date. The cleaning pipeline therefore uses a two-stage payment/subscription link: active-window match first, then most-recent prior subscription as an auditable fallback. Final unresolved subscription links: 0.

## 3. Modeling design decision

A naive merge of all historical events can introduce post-churn leakage. The implemented feature store uses a customer-specific anchor:

- churned customer: `anchor_date = churn_date`
- non-churned customer: `anchor_date = 2026-06-30` (latest observed event date)

Viewing, billing, ticket, and feedback features are restricted to events on or before the anchor. This is more defensible for a portfolio churn system.

## 4. Feature groups

**Engagement:** recency, 30/90-day sessions, watch minutes, prior-period change, six-bin watch trend, completion, active days, device diversity, genre diversity, login frequency.

**Billing:** recent payment count, failed-payment count/rate, days since failed payment, successful lifetime spend.

**Support:** lifetime/recent ticket count, average CSAT, resolution time, low-CSAT rate, high-priority tickets.

**Feedback:** recent count, average rating, negative-feedback count/rate.

**Subscription:** tenure, current plan/price, auto-renew, plan-change count.

**Business composites:** engagement score, billing risk score, support friction score.

## 5. ML architecture

### Churn classification

Candidates: Logistic Regression, Random Forest, XGBoost. The training script performs stratified cross-validation and chooses the best ROC-AUC model. A separate F2-optimized threshold is selected from out-of-fold training predictions to favor recall in a retention workflow.

### Segmentation

K-Means is evaluated for K=2..7 with silhouette score. Cluster profiles are automatically summarized and assigned business-readable names. PCA coordinates support 2-D visualization.

### CLV regression

Ridge, Random Forest, and XGBoost are compared using MAE, RMSE, and R². Direct accounting proxies such as successful-payment count are excluded so the model cannot simply reconstruct the target mechanically.

## 6. GenAI copilot architecture

1. **Text-to-SQL:** live schema prompt → LLM SQL → SQLGlot validation → read-only execution → result explanation. Includes single-statement enforcement, DML/DDL blocking, table/column validation, row cap, statement timeout, and audit logging.
2. **RAG support intelligence:** support and feedback text → embeddings → FAISS → top-k evidence → grounded answer with record IDs.
3. **Prediction explainer:** churn probability + SHAP/model contributions + business features → constrained natural-language explanation.
4. **Business report generator:** calculated SQL facts → executive narrative with facts separated from interpretation.
5. **Root-cause agent:** fixed diagnostic sequence for churn, engagement, payment failures, support/CSAT, and plan mix.
6. **Retention recommender:** deterministic policy using risk, CLV, segment, engagement, billing, and support; LLM only explains/phrases the action.

## 7. Portfolio positioning recommendation

Use wording such as **“modeled on Netflix's subscription business using synthetic data.”** Avoid implying the files are real Netflix customer records, internal Netflix analytics, or a system built for Netflix.

The strongest differentiator is not the brand name; it is the combination of **analytics engineering + leakage-aware ML + explainability + secured GenAI workflows + deployable Streamlit product**.
