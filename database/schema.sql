CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(12) PRIMARY KEY,
    first_name VARCHAR(50), last_name VARCHAR(50), age SMALLINT,
    gender VARCHAR(25), country VARCHAR(60), state_or_region VARCHAR(60), city VARCHAR(60),
    registration_date DATE, acquisition_channel VARCHAR(50), customer_segment VARCHAR(30),
    preferred_language VARCHAR(30)
);
CREATE TABLE IF NOT EXISTS subscription_plans (
    plan_id VARCHAR(10) PRIMARY KEY, plan_name VARCHAR(30) NOT NULL,
    monthly_price NUMERIC(6,2) NOT NULL, video_quality VARCHAR(30), max_devices SMALLINT,
    advertisements VARCHAR(5)
);
CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id VARCHAR(12) PRIMARY KEY,
    customer_id VARCHAR(12) NOT NULL REFERENCES customers(customer_id),
    plan_id VARCHAR(10) NOT NULL REFERENCES subscription_plans(plan_id),
    subscription_start_date DATE NOT NULL, subscription_end_date DATE,
    subscription_status VARCHAR(20), auto_renew BOOLEAN, cancellation_date DATE,
    cancellation_reason VARCHAR(80), monthly_price NUMERIC(6,2)
);
CREATE TABLE IF NOT EXISTS content (
    content_id VARCHAR(10) PRIMARY KEY, title VARCHAR(150) NOT NULL,
    content_type VARCHAR(30), genre VARCHAR(30), release_year SMALLINT,
    duration_minutes SMALLINT, content_language VARCHAR(30), production_country VARCHAR(60),
    maturity_rating VARCHAR(10)
);
CREATE TABLE IF NOT EXISTS viewing_activity (
    viewing_id VARCHAR(14) PRIMARY KEY,
    customer_id VARCHAR(12) NOT NULL REFERENCES customers(customer_id),
    content_id VARCHAR(10) NOT NULL REFERENCES content(content_id),
    viewing_date DATE NOT NULL, watch_duration_minutes SMALLINT,
    completion_percentage NUMERIC(5,2), device_type VARCHAR(30), login_location VARCHAR(60),
    session_duration_minutes SMALLINT
);
CREATE TABLE IF NOT EXISTS payments (
    payment_id VARCHAR(14) PRIMARY KEY,
    customer_id VARCHAR(12) NOT NULL REFERENCES customers(customer_id),
    subscription_id VARCHAR(12) REFERENCES subscriptions(subscription_id),
    payment_date DATE NOT NULL, amount NUMERIC(7,2), payment_method VARCHAR(30),
    payment_status VARCHAR(15), failed_payment_reason VARCHAR(60)
);
CREATE TABLE IF NOT EXISTS support_tickets (
    ticket_id VARCHAR(12) PRIMARY KEY,
    customer_id VARCHAR(12) NOT NULL REFERENCES customers(customer_id),
    ticket_date DATE, issue_category VARCHAR(40), issue_subcategory VARCHAR(60), priority VARCHAR(15),
    ticket_status VARCHAR(15), resolution_time_hours NUMERIC(6,1),
    customer_satisfaction_score SMALLINT, ticket_description TEXT, support_agent_id VARCHAR(10)
);
CREATE TABLE IF NOT EXISTS customer_feedback (
    feedback_id VARCHAR(12) PRIMARY KEY,
    customer_id VARCHAR(12) NOT NULL REFERENCES customers(customer_id),
    feedback_date DATE, rating SMALLINT, feedback_text TEXT, sentiment_label VARCHAR(15)
);
CREATE TABLE IF NOT EXISTS churn_labels (
    customer_id VARCHAR(12) PRIMARY KEY REFERENCES customers(customer_id),
    churned BOOLEAN NOT NULL, churn_date DATE, churn_reason VARCHAR(80)
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_customer ON subscriptions(customer_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_plan ON subscriptions(plan_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(subscription_status);
CREATE INDEX IF NOT EXISTS idx_viewing_customer ON viewing_activity(customer_id);
CREATE INDEX IF NOT EXISTS idx_viewing_content ON viewing_activity(content_id);
CREATE INDEX IF NOT EXISTS idx_viewing_date ON viewing_activity(viewing_date);
CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_id);
CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(payment_status);
CREATE INDEX IF NOT EXISTS idx_tickets_customer ON support_tickets(customer_id);
CREATE INDEX IF NOT EXISTS idx_tickets_category ON support_tickets(issue_category);
CREATE INDEX IF NOT EXISTS idx_tickets_date ON support_tickets(ticket_date);
CREATE INDEX IF NOT EXISTS idx_feedback_customer ON customer_feedback(customer_id);
CREATE INDEX IF NOT EXISTS idx_feedback_sentiment ON customer_feedback(sentiment_label);
CREATE INDEX IF NOT EXISTS idx_customers_country ON customers(country);
CREATE INDEX IF NOT EXISTS idx_customers_segment ON customers(customer_segment);
