# 🎬 Customer Intelligence & AI Analytics Copilot

An end-to-end **Data Science, Machine Learning, SQL, and Generative AI** project for customer analytics in a streaming subscription business.

> **Disclaimer:** This is an independent portfolio project using **synthetic data**. It does not contain real Netflix customer data and is not affiliated with Netflix.

## 🚀 Features

- 📊 Interactive Streamlit analytics dashboard
- 🎯 Customer churn prediction
- 👥 Customer segmentation using K-Means
- 💰 Customer Lifetime Value (CLV) prediction
- 🔍 Explainable AI using SHAP
- 🗄️ PostgreSQL analytics
- 🤖 Natural-language Text-to-SQL Copilot
- 📚 RAG using SentenceTransformers + FAISS
- 💡 AI-assisted retention recommendations
- 📈 Automated root-cause analysis and reporting

## 🛠️ Tech Stack

**Python | PostgreSQL | Pandas | Scikit-learn | XGBoost | SHAP | Streamlit | FAISS | SentenceTransformers | OpenAI/Ollama | Docker**

## 🏗️ Project Structure

```text
├── app/          # Streamlit dashboard
├── data/         # Synthetic datasets
├── database/     # PostgreSQL schema & queries
├── notebooks/    # EDA and ML experiments
├── src/          # ML, RAG, SQL & application logic
├── scripts/      # Setup and utility scripts
├── tests/        # Automated tests
└── docker-compose.yml
```

## ⚙️ Installation

```bash
git clone https://github.com/Poonam4385/netflix_customer_intelligence_ai_copilot-Internmo.git
cd netflix_customer_intelligence_ai_copilot-Internmo

python -m venv .venv
pip install -r requirements.txt
```

Create your local environment file from `.env.example`.

**Never commit your `.env`, API keys, passwords, or database credentials.**

## ▶️ Run the Application

Start PostgreSQL:

```bash
docker compose up -d db
```

Run the Streamlit dashboard:

```bash
python -m streamlit run app/dashboard.py
```

Open:

```text
http://localhost:8501
```

## 📊 ML Models

| Task | Model/Method |
|---|---|
| Churn Prediction | XGBoost |
| Customer Segmentation | K-Means |
| Customer Lifetime Value | XGBoost |
| Explainability | SHAP |
| Semantic Search | FAISS + SentenceTransformers |

## 🔐 Privacy & Security

- Uses synthetic customer data only
- API keys are stored through environment variables
- `.env` is excluded from Git
- Text-to-SQL restricts destructive SQL operations
- Generated logs and RAG indexes remain local

## 📌 Disclaimer

This project was created for **educational and portfolio purposes**.

Netflix is a trademark of Netflix, Inc. This project is not affiliated with, endorsed by, or sponsored by Netflix.
