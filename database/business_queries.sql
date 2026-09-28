-- Netflix Customer Intelligence: 37 business questions (PostgreSQL)
-- Queries use the maximum available dataset date where a relative "current" period is needed.

-- Q01 Active customers by country
SELECT c.country, COUNT(DISTINCT c.customer_id) AS active_customers
FROM customers c JOIN subscriptions s ON s.customer_id=c.customer_id
WHERE s.subscription_status='Active'
GROUP BY c.country ORDER BY active_customers DESC;

-- Q02 Total and average monthly revenue by active subscription plan
SELECT sp.plan_name, COUNT(*) AS active_subscriptions,
       SUM(s.monthly_price) AS monthly_revenue,
       AVG(s.monthly_price) AS avg_monthly_revenue_per_subscription
FROM subscriptions s JOIN subscription_plans sp ON sp.plan_id=s.plan_id
WHERE s.subscription_status='Active'
GROUP BY sp.plan_name ORDER BY monthly_revenue DESC;

-- Q03 Overall churn rate
SELECT COUNT(*) AS customers,
       SUM(CASE WHEN churned THEN 1 ELSE 0 END) AS churned_customers,
       ROUND(100.0*AVG(CASE WHEN churned THEN 1.0 ELSE 0.0 END),2) AS churn_rate_pct
FROM churn_labels;

-- Q04 Acquisition channel customer volume and churn rate
SELECT c.acquisition_channel, COUNT(*) AS customers,
       ROUND(100.0*AVG(CASE WHEN cl.churned THEN 1.0 ELSE 0.0 END),2) AS churn_rate_pct
FROM customers c JOIN churn_labels cl USING(customer_id)
GROUP BY c.acquisition_channel ORDER BY customers DESC;

-- Q05 Average age by current/latest subscription plan
WITH latest AS (
 SELECT s.*, ROW_NUMBER() OVER(PARTITION BY customer_id ORDER BY subscription_start_date DESC, subscription_id DESC) rn
 FROM subscriptions s
)
SELECT sp.plan_name, ROUND(AVG(c.age),2) AS avg_customer_age
FROM latest s JOIN customers c USING(customer_id) JOIN subscription_plans sp USING(plan_id)
WHERE s.rn=1 GROUP BY sp.plan_name ORDER BY avg_customer_age;

-- Q06 Top 10 most-watched titles
SELECT ct.content_id, ct.title, SUM(v.watch_duration_minutes) AS total_watch_minutes
FROM viewing_activity v JOIN content ct USING(content_id)
GROUP BY ct.content_id, ct.title ORDER BY total_watch_minutes DESC LIMIT 10;

-- Q07 Average completion by content type and genre
SELECT ct.content_type, ct.genre, ROUND(AVG(v.completion_percentage),2) AS avg_completion_pct,
       COUNT(*) AS sessions
FROM viewing_activity v JOIN content ct USING(content_id)
GROUP BY ct.content_type, ct.genre ORDER BY ct.content_type, avg_completion_pct DESC;

-- Q08 Failed payments by month, last 12 months of data
WITH a AS (SELECT DATE_TRUNC('month',MAX(payment_date)) AS max_month FROM payments)
SELECT DATE_TRUNC('month',p.payment_date)::date AS month, COUNT(*) AS failed_payments
FROM payments p CROSS JOIN a
WHERE p.payment_status='Failed' AND p.payment_date >= a.max_month - INTERVAL '11 months'
GROUP BY 1 ORDER BY 1;

-- Q09 Average support resolution time by category
SELECT issue_category, ROUND(AVG(resolution_time_hours),2) AS avg_resolution_hours, COUNT(*) AS resolved_tickets
FROM support_tickets
WHERE ticket_status IN ('Resolved','Closed') AND resolution_time_hours IS NOT NULL
GROUP BY issue_category ORDER BY avg_resolution_hours DESC;

-- Q10 CSAT distribution across resolved/closed tickets
SELECT customer_satisfaction_score, COUNT(*) AS tickets,
       ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER(),2) AS pct_of_resolved
FROM support_tickets
WHERE ticket_status IN ('Resolved','Closed') AND customer_satisfaction_score IS NOT NULL
GROUP BY customer_satisfaction_score ORDER BY customer_satisfaction_score;

-- Q11 Device generating the most total viewing minutes
SELECT device_type, SUM(watch_duration_minutes) AS total_viewing_minutes, COUNT(*) AS sessions
FROM viewing_activity GROUP BY device_type ORDER BY total_viewing_minutes DESC;

-- Q12 Average feedback rating by supplied sentiment label
SELECT sentiment_label, ROUND(AVG(rating),2) AS avg_rating, COUNT(*) AS feedback_count
FROM customer_feedback GROUP BY sentiment_label ORDER BY avg_rating DESC;

-- Q13 Signups by acquisition channel and year
SELECT EXTRACT(YEAR FROM registration_date)::int AS registration_year, acquisition_channel, COUNT(*) AS signups
FROM customers GROUP BY 1,2 ORDER BY 1, signups DESC;

-- Q14 Percentage of customers with auto-renew off on latest subscription
WITH latest AS (
 SELECT s.*, ROW_NUMBER() OVER(PARTITION BY customer_id ORDER BY subscription_start_date DESC, subscription_id DESC) rn
 FROM subscriptions s
)
SELECT COUNT(*) AS customers,
       SUM(CASE WHEN NOT auto_renew THEN 1 ELSE 0 END) AS auto_renew_off,
       ROUND(100.0*AVG(CASE WHEN NOT auto_renew THEN 1.0 ELSE 0.0 END),2) AS auto_renew_off_pct
FROM latest WHERE rn=1;

-- Q15 Customers with >3 support tickets
SELECT c.customer_id, c.first_name, c.last_name, COUNT(t.ticket_id) AS ticket_count
FROM customers c JOIN support_tickets t USING(customer_id)
GROUP BY c.customer_id,c.first_name,c.last_name HAVING COUNT(t.ticket_id)>3
ORDER BY ticket_count DESC, c.customer_id;

-- Q16 Rank plans by active monthly revenue
WITH r AS (
 SELECT sp.plan_name, SUM(s.monthly_price) AS total_revenue
 FROM subscriptions s JOIN subscription_plans sp USING(plan_id)
 WHERE s.subscription_status='Active' GROUP BY sp.plan_name
)
SELECT *, RANK() OVER(ORDER BY total_revenue DESC) AS revenue_rank FROM r ORDER BY revenue_rank;

-- Q17 Most recent support ticket per customer
WITH ranked AS (
 SELECT t.*, ROW_NUMBER() OVER(PARTITION BY customer_id ORDER BY ticket_date DESC NULLS LAST, ticket_id DESC) rn
 FROM support_tickets t
)
SELECT * FROM ranked WHERE rn=1;

-- Q18 3-month moving average of registrations
WITH m AS (
 SELECT DATE_TRUNC('month',registration_date)::date AS month, COUNT(*) AS registrations
 FROM customers GROUP BY 1
)
SELECT month, registrations,
       ROUND(AVG(registrations) OVER(ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW),2) AS registrations_3m_ma
FROM m ORDER BY month;

-- Q19 Customers with latest month watch time lower than prior month
WITH m AS (
 SELECT customer_id, DATE_TRUNC('month',viewing_date)::date AS month, SUM(watch_duration_minutes) AS watch_minutes
 FROM viewing_activity GROUP BY 1,2
), x AS (
 SELECT *, LAG(watch_minutes) OVER(PARTITION BY customer_id ORDER BY month) AS prior_month_watch,
        ROW_NUMBER() OVER(PARTITION BY customer_id ORDER BY month DESC) AS rn
 FROM m
)
SELECT customer_id, month, watch_minutes, prior_month_watch,
       (watch_minutes < prior_month_watch) AS mom_decline_flag
FROM x WHERE rn=1 AND prior_month_watch IS NOT NULL AND watch_minutes < prior_month_watch
ORDER BY customer_id;

-- Q20 Registration cohort retention at 1, 3, and 6 months
WITH base AS (
 SELECT c.customer_id, DATE_TRUNC('month',c.registration_date)::date AS cohort_month, c.registration_date
 FROM customers c
), flags AS (
 SELECT b.*,
   EXISTS(SELECT 1 FROM subscriptions s WHERE s.customer_id=b.customer_id
          AND s.subscription_start_date <= b.registration_date + INTERVAL '1 month'
          AND COALESCE(s.subscription_end_date,s.cancellation_date,DATE '9999-12-31') >= b.registration_date + INTERVAL '1 month') AS r1,
   EXISTS(SELECT 1 FROM subscriptions s WHERE s.customer_id=b.customer_id
          AND s.subscription_start_date <= b.registration_date + INTERVAL '3 months'
          AND COALESCE(s.subscription_end_date,s.cancellation_date,DATE '9999-12-31') >= b.registration_date + INTERVAL '3 months') AS r3,
   EXISTS(SELECT 1 FROM subscriptions s WHERE s.customer_id=b.customer_id
          AND s.subscription_start_date <= b.registration_date + INTERVAL '6 months'
          AND COALESCE(s.subscription_end_date,s.cancellation_date,DATE '9999-12-31') >= b.registration_date + INTERVAL '6 months') AS r6
 FROM base b
)
SELECT cohort_month, COUNT(*) AS cohort_size,
 ROUND(100.0*AVG(r1::int),2) AS retention_1m_pct,
 ROUND(100.0*AVG(r3::int),2) AS retention_3m_pct,
 ROUND(100.0*AVG(r6::int),2) AS retention_6m_pct
FROM flags GROUP BY cohort_month ORDER BY cohort_month;

-- Q21 Top 5 countries by churn rate using DENSE_RANK
WITH c AS (
 SELECT cu.country, COUNT(*) total_customers, SUM(cl.churned::int) churned_customers,
        AVG(cl.churned::int::numeric) churn_rate
 FROM customers cu JOIN churn_labels cl USING(customer_id) GROUP BY cu.country
), r AS (
 SELECT *, DENSE_RANK() OVER(ORDER BY churn_rate DESC) AS churn_rank FROM c
)
SELECT country,total_customers,churned_customers,ROUND(100*churn_rate,2) churn_rate_pct,churn_rank
FROM r WHERE churn_rank<=5 ORDER BY churn_rank,country;

-- Q22 Running total of successful payments per customer
SELECT customer_id,payment_id,payment_date,amount,payment_status,
       SUM(CASE WHEN payment_status='Success' THEN amount ELSE 0 END)
       OVER(PARTITION BY customer_id ORDER BY payment_date,payment_id ROWS UNBOUNDED PRECEDING) AS running_successful_spend
FROM payments ORDER BY customer_id,payment_date,payment_id;

-- Q23 Three consecutive months of declining watch time
WITH m AS (
 SELECT customer_id,DATE_TRUNC('month',viewing_date)::date month,SUM(watch_duration_minutes) watch_minutes
 FROM viewing_activity GROUP BY 1,2
), l AS (
 SELECT *,LAG(watch_minutes,1) OVER(PARTITION BY customer_id ORDER BY month) m1,
          LAG(watch_minutes,2) OVER(PARTITION BY customer_id ORDER BY month) m2
 FROM m
)
SELECT customer_id,month,watch_minutes AS month_n,m1 AS month_n_minus_1,m2 AS month_n_minus_2
FROM l WHERE watch_minutes<m1 AND m1<m2 ORDER BY customer_id,month;

-- Q24 Monthly churn rate over last 12 months
WITH anchor AS (SELECT DATE_TRUNC('month',MAX(churn_date)) AS max_month FROM churn_labels),
months AS (
 SELECT generate_series(a.max_month-INTERVAL '11 months',a.max_month,INTERVAL '1 month')::date AS month_start FROM anchor a
), calc AS (
 SELECT m.month_start,
   COUNT(*) FILTER(WHERE c.registration_date < m.month_start AND (cl.churn_date IS NULL OR cl.churn_date >= m.month_start)) AS active_at_start,
   COUNT(*) FILTER(WHERE cl.churn_date >= m.month_start AND cl.churn_date < m.month_start+INTERVAL '1 month') AS churned_in_month
 FROM months m CROSS JOIN customers c JOIN churn_labels cl USING(customer_id)
 GROUP BY m.month_start
)
SELECT *,ROUND(100.0*churned_in_month/NULLIF(active_at_start,0),2) AS churn_rate_pct FROM calc ORDER BY month_start;

-- Q25 Retention rate by acquisition channel
SELECT c.acquisition_channel,COUNT(*) acquired_customers,
       SUM((NOT cl.churned)::int) retained_customers,
       ROUND(100.0*AVG((NOT cl.churned)::int),2) retention_rate_pct
FROM customers c JOIN churn_labels cl USING(customer_id)
GROUP BY c.acquisition_channel ORDER BY retention_rate_pct DESC;

-- Q26 Lifetime successful spend and NTILE quartiles
WITH clv AS (
 SELECT c.customer_id,COALESCE(SUM(CASE WHEN p.payment_status='Success' THEN p.amount ELSE 0 END),0) lifetime_spend
 FROM customers c LEFT JOIN payments p USING(customer_id) GROUP BY c.customer_id
)
SELECT customer_id,lifetime_spend,NTILE(4) OVER(ORDER BY lifetime_spend) AS clv_quartile
FROM clv ORDER BY lifetime_spend DESC;

-- Q27 Top 3 issue subcategories by ticket volume, per country
WITH counts AS (
 SELECT c.country,t.issue_subcategory,COUNT(*) ticket_volume
 FROM support_tickets t JOIN customers c USING(customer_id)
 GROUP BY c.country,t.issue_subcategory
), r AS (
 SELECT *,ROW_NUMBER() OVER(PARTITION BY country ORDER BY ticket_volume DESC,issue_subcategory) rn FROM counts
)
SELECT country,issue_subcategory,ticket_volume,rn AS country_rank FROM r WHERE rn<=3 ORDER BY country,rn;

-- Q28 2+ failed payments in last 90 days and high SQL churn-risk proxy
WITH a AS (SELECT MAX(payment_date) max_date FROM payments),
failed AS (
 SELECT p.customer_id,COUNT(*) failed_payment_count
 FROM payments p CROSS JOIN a WHERE p.payment_status='Failed' AND p.payment_date>a.max_date-INTERVAL '90 days'
 GROUP BY p.customer_id HAVING COUNT(*)>=2
), activity AS (
 SELECT c.customer_id,COALESCE((SELECT MAX(v.viewing_date) FROM viewing_activity v WHERE v.customer_id=c.customer_id),DATE '1900-01-01') last_view,
        (SELECT COUNT(*) FROM support_tickets t CROSS JOIN a WHERE t.customer_id=c.customer_id AND t.ticket_date>a.max_date-INTERVAL '90 days') recent_tickets
 FROM customers c
), latest AS (
 SELECT *,ROW_NUMBER() OVER(PARTITION BY customer_id ORDER BY subscription_start_date DESC) rn FROM subscriptions
), a2 AS (SELECT max_date FROM a)
SELECT f.customer_id,f.failed_payment_count,sp.plan_name AS current_plan,
       (a2.max_date-ac.last_view) AS days_since_last_activity,ac.recent_tickets
FROM failed f JOIN activity ac USING(customer_id) JOIN latest s USING(customer_id)
JOIN subscription_plans sp USING(plan_id) CROSS JOIN a2
WHERE s.rn=1 AND ((a2.max_date-ac.last_view)>30 OR ac.recent_tickets>=2)
ORDER BY f.failed_payment_count DESC,(a2.max_date-ac.last_view) DESC;

-- Q29 Engagement 30 days before/after most recent subscription price change
WITH x AS (
 SELECT s.*,LAG(monthly_price) OVER(PARTITION BY customer_id ORDER BY subscription_start_date) old_price,
        ROW_NUMBER() OVER(PARTITION BY customer_id ORDER BY subscription_start_date DESC) rn_desc
 FROM subscriptions s
), changes AS (
 SELECT customer_id,subscription_start_date change_date,old_price,monthly_price new_price,
        ROW_NUMBER() OVER(PARTITION BY customer_id ORDER BY subscription_start_date DESC) rn
 FROM x WHERE old_price IS DISTINCT FROM monthly_price
), recent AS (SELECT * FROM changes WHERE rn=1),
agg AS (
 SELECT r.customer_id,r.change_date,r.old_price,r.new_price,
   AVG(v.watch_duration_minutes) FILTER(WHERE v.viewing_date>=r.change_date-INTERVAL '30 days' AND v.viewing_date<r.change_date) avg_watch_before,
   AVG(v.watch_duration_minutes) FILTER(WHERE v.viewing_date>=r.change_date AND v.viewing_date<r.change_date+INTERVAL '30 days') avg_watch_after
 FROM recent r LEFT JOIN viewing_activity v ON v.customer_id=r.customer_id
 GROUP BY r.customer_id,r.change_date,r.old_price,r.new_price
)
SELECT *,ROUND(100.0*(avg_watch_after-avg_watch_before)/NULLIF(avg_watch_before,0),2) pct_change
FROM agg ORDER BY pct_change NULLS LAST;

-- Q30 Country customer/churn/CLV/top churn reason
WITH base AS (
 SELECT c.country,c.customer_id,cl.churned,cl.churn_reason,
        COALESCE(SUM(CASE WHEN p.payment_status='Success' THEN p.amount ELSE 0 END),0) clv
 FROM customers c JOIN churn_labels cl USING(customer_id) LEFT JOIN payments p USING(customer_id)
 GROUP BY c.country,c.customer_id,cl.churned,cl.churn_reason
), reason AS (
 SELECT country,churn_reason,COUNT(*) n,ROW_NUMBER() OVER(PARTITION BY country ORDER BY COUNT(*) DESC,churn_reason) rn
 FROM base WHERE churned GROUP BY country,churn_reason
), stats AS (
 SELECT country,COUNT(*) total_customers,SUM(churned::int) churned_customers,
        100.0*AVG(churned::int) churn_rate_pct,
        AVG(clv) FILTER(WHERE churned) avg_clv_churned
 FROM base GROUP BY country
)
SELECT s.country,s.total_customers,s.churned_customers,ROUND(s.churn_rate_pct,2) churn_rate_pct,
       ROUND(s.avg_clv_churned,2) avg_clv_churned,r.churn_reason AS top_churn_reason
FROM stats s LEFT JOIN reason r ON r.country=s.country AND r.rn=1 ORDER BY churn_rate_pct DESC;

-- Q31 At-risk revenue: normalized recency + payment failures + support volume
WITH anchor AS (SELECT GREATEST((SELECT MAX(viewing_date) FROM viewing_activity),(SELECT MAX(payment_date) FROM payments)) max_date),
latest AS (
 SELECT *,ROW_NUMBER() OVER(PARTITION BY customer_id ORDER BY subscription_start_date DESC) rn FROM subscriptions
), raw AS (
 SELECT c.customer_id,s.monthly_price,
  COALESCE((a.max_date-MAX(v.viewing_date)),999) recency_days,
  COALESCE(AVG(CASE WHEN p.payment_status='Failed' THEN 1.0 ELSE 0.0 END),0) failed_rate,
  COUNT(DISTINCT t.ticket_id) ticket_count
 FROM customers c JOIN latest s ON s.customer_id=c.customer_id AND s.rn=1 CROSS JOIN anchor a
 LEFT JOIN viewing_activity v ON v.customer_id=c.customer_id
 LEFT JOIN payments p ON p.customer_id=c.customer_id
 LEFT JOIN support_tickets t ON t.customer_id=c.customer_id
 WHERE s.subscription_status='Active'
 GROUP BY c.customer_id,s.monthly_price,a.max_date
), n AS (
 SELECT *,PERCENT_RANK() OVER(ORDER BY recency_days) n_recency,
          PERCENT_RANK() OVER(ORDER BY failed_rate) n_failed,
          PERCENT_RANK() OVER(ORDER BY ticket_count) n_tickets
 FROM raw
)
SELECT customer_id,monthly_price,recency_days,failed_rate,ticket_count,
       ROUND(100*(.45*n_recency+.35*n_failed+.20*n_tickets),2) sql_churn_risk_score,
       ROUND(monthly_price*(.45*n_recency+.35*n_failed+.20*n_tickets),2) at_risk_revenue
FROM n ORDER BY at_risk_revenue DESC LIMIT 50;

-- Q32 Top 5 complaints per country, most recent completed quarter
WITH a AS (SELECT DATE_TRUNC('quarter',MAX(ticket_date))::date current_q FROM support_tickets),
q AS (
 SELECT c.country,t.issue_subcategory,COUNT(*) ticket_volume,
        AVG(t.resolution_time_hours) avg_resolution_hours,AVG(t.customer_satisfaction_score) avg_csat
 FROM support_tickets t JOIN customers c USING(customer_id) CROSS JOIN a
 WHERE t.ticket_date>=a.current_q-INTERVAL '3 months' AND t.ticket_date<a.current_q
 GROUP BY c.country,t.issue_subcategory
), r AS (
 SELECT *,ROW_NUMBER() OVER(PARTITION BY country ORDER BY ticket_volume DESC,issue_subcategory) rn FROM q
)
SELECT country,issue_subcategory,ticket_volume,ROUND(avg_resolution_hours,2) avg_resolution_hours,
       ROUND(avg_csat,2) avg_csat,rn FROM r WHERE rn<=5 ORDER BY country,rn;

-- Q33 Win-back candidates: churned + top-quartile CLV, with last 30d engagement
WITH clv AS (
 SELECT c.customer_id,COALESCE(SUM(CASE WHEN p.payment_status='Success' THEN p.amount ELSE 0 END),0) clv
 FROM customers c LEFT JOIN payments p USING(customer_id) GROUP BY c.customer_id
), q AS (
 SELECT *,NTILE(4) OVER(ORDER BY clv) q FROM clv
), eng AS (
 SELECT cl.customer_id,cl.churn_date,SUM(v.watch_duration_minutes) AS last30_watch_minutes
 FROM churn_labels cl LEFT JOIN viewing_activity v ON v.customer_id=cl.customer_id
  AND v.viewing_date>=cl.churn_date-INTERVAL '30 days' AND v.viewing_date<=cl.churn_date
 WHERE cl.churned GROUP BY cl.customer_id,cl.churn_date
)
SELECT q.customer_id,q.clv,cl.churn_reason,COALESCE(e.last30_watch_minutes,0) last30_watch_minutes,
       CASE WHEN COALESCE(e.last30_watch_minutes,0)>=600 THEN 'High'
            WHEN COALESCE(e.last30_watch_minutes,0)>=180 THEN 'Medium' ELSE 'Low' END last_engagement_level
FROM q JOIN churn_labels cl USING(customer_id) LEFT JOIN eng e USING(customer_id)
WHERE cl.churned AND q.q=4 ORDER BY q.clv DESC;

-- Q34 Plan migration paths and churn rate for upgrades vs downgrades
WITH ordered AS (
 SELECT s.customer_id,s.subscription_start_date,s.plan_id,
        LEAD(s.plan_id) OVER(PARTITION BY s.customer_id ORDER BY s.subscription_start_date) next_plan_id
 FROM subscriptions s
), mig AS (
 SELECT o.customer_id,sp1.plan_name from_plan,sp2.plan_name to_plan,
        CASE WHEN sp2.monthly_price>sp1.monthly_price THEN 'Upgrade'
             WHEN sp2.monthly_price<sp1.monthly_price THEN 'Downgrade' ELSE 'Same-price/Other' END direction
 FROM ordered o JOIN subscription_plans sp1 ON sp1.plan_id=o.plan_id
 JOIN subscription_plans sp2 ON sp2.plan_id=o.next_plan_id WHERE o.next_plan_id IS NOT NULL
)
SELECT from_plan,to_plan,direction,COUNT(*) migrations,
       ROUND(100.0*AVG(cl.churned::int),2) churn_rate_pct
FROM mig m JOIN churn_labels cl USING(customer_id)
GROUP BY from_plan,to_plan,direction ORDER BY migrations DESC;

-- Q35 WAU / MAU and stickiness, last 6 months
WITH a AS (SELECT DATE_TRUNC('month',MAX(viewing_date)) max_month FROM viewing_activity),
weeks AS (
 SELECT DATE_TRUNC('week',v.viewing_date)::date week_start,
        DATE_TRUNC('month',v.viewing_date)::date month,COUNT(DISTINCT v.customer_id) wau
 FROM viewing_activity v CROSS JOIN a
 WHERE v.viewing_date>=a.max_month-INTERVAL '5 months' GROUP BY 1,2
), wau_m AS (SELECT month,AVG(wau) avg_wau FROM weeks GROUP BY month),
mau AS (
 SELECT DATE_TRUNC('month',v.viewing_date)::date month,COUNT(DISTINCT v.customer_id) mau
 FROM viewing_activity v CROSS JOIN a WHERE v.viewing_date>=a.max_month-INTERVAL '5 months' GROUP BY 1
)
SELECT m.month,ROUND(w.avg_wau,2) avg_wau,m.mau,ROUND(100.0*w.avg_wau/NULLIF(m.mau,0),2) wau_mau_stickiness_pct
FROM mau m JOIN wau_m w USING(month) ORDER BY m.month;

-- Q36 Negative feedback within 14 days of failed payment or low-CSAT support ticket
SELECT DISTINCT f.customer_id,f.feedback_id,f.feedback_date,f.rating,f.feedback_text
FROM customer_feedback f
WHERE f.rating<=2 AND (
 EXISTS(SELECT 1 FROM payments p WHERE p.customer_id=f.customer_id AND p.payment_status='Failed'
        AND ABS(f.feedback_date-p.payment_date)<=14)
 OR EXISTS(SELECT 1 FROM support_tickets t WHERE t.customer_id=f.customer_id AND t.customer_satisfaction_score<=2
        AND ABS(f.feedback_date-t.ticket_date)<=14)
)
ORDER BY f.feedback_date DESC;

-- Q37 Full customer health/risk score 0-100
WITH a AS (SELECT MAX(viewing_date) max_view FROM viewing_activity),
latest AS (SELECT *,ROW_NUMBER() OVER(PARTITION BY customer_id ORDER BY subscription_start_date DESC) rn FROM subscriptions),
raw AS (
 SELECT c.customer_id,sp.plan_name,
   COALESCE((a.max_view-MAX(v.viewing_date)),999) recency_days,
   COALESCE(AVG(CASE WHEN p.payment_status='Failed' THEN 1.0 ELSE 0.0 END),0) failed_payment_rate,
   COALESCE(AVG(t.customer_satisfaction_score),3) avg_support_satisfaction,
   (a.max_view-c.registration_date) tenure_days
 FROM customers c CROSS JOIN a JOIN latest s ON s.customer_id=c.customer_id AND s.rn=1 JOIN subscription_plans sp USING(plan_id)
 LEFT JOIN viewing_activity v ON v.customer_id=c.customer_id
 LEFT JOIN payments p ON p.customer_id=c.customer_id
 LEFT JOIN support_tickets t ON t.customer_id=c.customer_id
 GROUP BY c.customer_id,sp.plan_name,a.max_view,c.registration_date
), n AS (
 SELECT *,PERCENT_RANK() OVER(ORDER BY recency_days) r_recency,
          PERCENT_RANK() OVER(ORDER BY failed_payment_rate) r_failed,
          PERCENT_RANK() OVER(ORDER BY avg_support_satisfaction DESC) r_bad_csat,
          PERCENT_RANK() OVER(ORDER BY tenure_days DESC) r_short_tenure
 FROM raw
)
SELECT customer_id,plan_name,recency_days,ROUND(failed_payment_rate,3) failed_payment_rate,
       ROUND(avg_support_satisfaction,2) avg_support_satisfaction,tenure_days,
       ROUND(100*(.35*r_recency+.30*r_failed+.20*r_bad_csat+.15*r_short_tenure),2) risk_score_0_100
FROM n ORDER BY risk_score_0_100 DESC;
