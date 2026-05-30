# Fast Fraud Rule Lookup Architecture using HBase

## Overview

This project implements a fast fraud-rule lookup architecture using Apache HBase for transaction storage and retrieval.

The system ingests credit card transaction data, stores it in HBase using an optimized row-key design, retrieves a card's recent transaction history, and applies rule-based fraud detection to generate risk assessments.

The architecture is designed to support rapid retrieval of a card's recent transactions using HBase prefix scans.

---

## Objective

Build a scalable fraud lookup system capable of:

* Storing transaction records in HBase
* Retrieving a card's last 5 transactions efficiently
* Applying fraud detection rules on recent transaction history
* Generating risk scores and recommendations
* Demonstrating millisecond-scale lookup performance

---

## Dataset

Dataset used:

**Credit Card Fraud Detection Dataset**

https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud

Place the downloaded file as:

data/creditcard.csv

---

## Architecture

creditcard.csv

↓

load_data.py

↓

Synthetic CardHash Generation

↓

RowKey = CardHash_PaddedTimestamp

↓

HBase FraudTxn Table

↓

lookup.py

↓

Retrieve Last 5 Transactions

↓

fraud_rules.py

↓

Risk Assessment

---

## HBase Schema

### Table

FraudTxn

### Column Family

TxnDetails

### Row Key Design

CardHash_PaddedTimestamp

Example:

f3063b02_0000000067

Benefits:

* Transactions belonging to the same card are stored together.
* Prefix scans retrieve transaction history efficiently.
* Lexicographic ordering preserves chronological ordering.
* Supports fast lookup of recent transactions.

---

## Fraud Rules Implemented

### 1. High Value Transaction Rule

Flags transactions whose amount exceeds a predefined threshold.

### 2. Velocity Rule

Flags cards performing multiple transactions within a short time window.

### 3. Previous Fraud History Rule

Increases risk if prior fraudulent transactions exist.

### 4. Amount Spike Rule

Flags sudden increases compared to historical spending behavior.

---

## Project Structure

fraud-lookup-hbase/

├── data/

│ └── README.txt

│

├── scripts/

│ ├── load_data.py

│ ├── lookup.py

│ └── fraud_rules.py

│

├── screenshots/

│ ├── hbase_scan.png

│ ├── load_success.png

│ └── lookup_result.png

│

├── README.md

├── requirements.txt

└── .gitignore

---

## Installation

### Clone Repository

git clone <repository-url>

cd fraud-lookup-hbase

### Install Dependencies

pip install -r requirements.txt

### Start HBase

Run HBase using Docker:

docker run -d --name hbase -p 16010:16010 -p 2181:2181 -p 9090:9090 harisekhon/hbase

---

## Running the Project

### Load Data into HBase

python scripts/load_data.py --input data/creditcard.csv --limit 5000

### Run Fraud Lookup

Random sample:

python scripts/lookup.py --sample 5

Specific card:

python scripts/lookup.py --card <CardHash>

---

## Sample Output

Card : f3063b02

Lookup Time: 46.66 ms

History : 5 prior transaction(s)

Last Transactions:

Time=0s Amount=$149.62

Time=4s Amount=$4.99

Time=33s Amount=$9.10

Time=50s Amount=$14.80

Time=67s Amount=$28.28

Risk Score : 0.25

Risk Level : MEDIUM

Decision : REVIEW

Triggered Rule:

VelocityRule

---

## Results

* Successfully loaded transaction data into HBase.
* Implemented CardHash_Time row-key design.
* Retrieved recent transaction history using HBase prefix scans.
* Applied rule-based fraud detection.
* Generated risk scores and recommendations.
* Demonstrated retrieval latency in milliseconds.

---

## Future Improvements

* Real-time transaction ingestion using Kafka.
* Spark Streaming integration.
* Machine Learning based fraud prediction.
* HBase cluster deployment for large-scale workloads.
* Dashboard for fraud monitoring and analytics.

---

## Technologies Used

* Python
* Apache HBase
* Docker
* HappyBase
* Pandas
* Kaggle Credit Card Fraud Dataset

---

## Author

Naga Vaishanavi
