CREATE OR REPLACE VIEW v_current_subscription AS
SELECT * FROM (
    SELECT s.*,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY subscription_start_date DESC, subscription_id DESC) AS rn
    FROM subscriptions s
) x WHERE rn = 1;

CREATE OR REPLACE VIEW v_customer_clv AS
SELECT c.customer_id,
       COALESCE(SUM(CASE WHEN p.payment_status='Success' THEN p.amount ELSE 0 END), 0) AS customer_lifetime_value
FROM customers c
LEFT JOIN payments p ON p.customer_id=c.customer_id
GROUP BY c.customer_id;

CREATE OR REPLACE VIEW v_customer_support_summary AS
SELECT c.customer_id,
       COUNT(t.ticket_id) AS ticket_count,
       AVG(t.customer_satisfaction_score) AS avg_csat,
       AVG(t.resolution_time_hours) AS avg_resolution_hours
FROM customers c
LEFT JOIN support_tickets t ON t.customer_id=c.customer_id
GROUP BY c.customer_id;
