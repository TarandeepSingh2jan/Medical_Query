# Medical RAG System

A Flask-based Retrieval-Augmented Generation (RAG) system that integrates a Neo4j graph database with OpenAI to provide natural language responses to medical queries. The system stores medical data (e.g., diseases, symptoms, precautions) and uses OpenAI's API for query processing and result summarization.

## Prerequisites

- Python 3.8+ (recommended: 3.9 or 3.10)
- Git (for cloning the repository)
- Neo4j Desktop or a Neo4j Aura account
- OpenRouter API key (for OpenAI integration)

## Setup Instructions

### 1. Clone the Repository
Clone this repository to your local machine and navigate to the project directory:
git clone https://github.com/yourusername/medical-rag-system.git
cd medical-rag-system

2. Install Dependencies

Create a virtual environment (optional but recommended for dependency management)
Install the required Python packages
If requirements.txt is not present, install dependencies manually

3. Database Setup (Neo4j Aura)
This project uses Neo4j to store and query medical data. We recommend using Neo4j Aura (cloud-based) for ease of setup, scalability, and collaboration.

Sign Up for Neo4j Aura:

Visit neo4j.com/aura and sign up for a free tier account.
Create a new database instance and note the following details:

URI: e.g., neo4j+s://9759301a.databases.neo4j.io
Username: neo4j
Password: Set during creation (save this securely)


Import Data:

Download sample CSV files (e.g., diseases.csv, symptoms.csv, precautions.csv, disease_symptom.csv, disease_precaution.csv) if not included in the data folder. If included, use those files.
Access the Neo4j Browser via the Aura dashboard:

Click the "Upload" button to upload each CSV file.
Run the following Cypher commands to import the data (adjust file paths if using local files or Aura URLs):

// Import Diseases
LOAD CSV WITH HEADERS FROM 'file:///diseases.csv' AS row
MERGE (d:Disease {name: row.Disease})
SET d.description = row.Description;

// Import Symptoms
LOAD CSV WITH HEADERS FROM 'file:///symptoms.csv' AS row
MERGE (s:Symptom {name: row.Symptom})
SET s.weight = toInteger(row.Weight);

// Import Precautions
LOAD CSV WITH HEADERS FROM 'file:///precautions.csv' AS row
MERGE (p:Precaution {name: row.Precaution});

// Create Relationships (Disease-Symptom)
LOAD CSV WITH HEADERS FROM 'file:///disease_symptom.csv' AS row
MATCH (d:Disease {name: row.Disease})
MATCH (s:Symptom {name: row.Symptom})
MERGE (s)-[:HAS_SYMPTOM]->(d);

// Create Relationships (Disease-Precaution)
LOAD CSV WITH HEADERS FROM 'file:///disease_precaution.csv' AS row
MATCH (d:Disease {name: row.Disease})
MATCH (p:Precaution {name: row.Precaution})
MERGE (d)-[:HAS_PRECAUTION]->(p);

Verify the data import with:
MATCH (d:Disease)-[:HAS_PRECAUTION]->(p:Precaution) RETURN d.name, collect(p.name) LIMIT 5;
If CSV files are not provided, contact the repository owner for data sources or use your own medical dataset.


4. OpenAI API Key Setup
This project uses the OpenRouter API to access OpenAI models for generating Cypher queries and summarizing results. An API key is required to enable this functionality.

Obtain an OpenRouter API Key:

Sign up at openrouter.ai.
Navigate to the API section, generate a new API key, and copy it (e.g., sk-...).
Keep this key secure and do not share it publicly.


Configure the API Key:

Create a .env file in the project root directory with the following content:

NEO4J_URI=neo4j+s://your-aura-uri
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_aura_password
OPENROUTER_API_KEY=your_openrouter_api_key

Replace your-aura-uri, your_aura_password, and your_openrouter_api_key with your actual Neo4j Aura URI, password, and OpenRouter API key, respectively.
Note: The .env file is excluded from version control. Ensure .gitignore includes .env to prevent accidental commits.