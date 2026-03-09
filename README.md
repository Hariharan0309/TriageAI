# TriageAI

TriageAI is an AI-powered platform that transforms IT service delivery. It moves beyond traditional automation to create a truly intelligent, self-managing service desk. The platform receives IT service requests, delegates them intelligently, and maintains interactions and context across support tickets and user sessions.

## 🏗 Architecture & Key Components

1. **Manager Agent (Vertex AI Reasoning Engine)**: 
   The core intelligence of TriageAI, built using the Google Cloud Agent Development Kit (ADK) and the Gemini-2.5-Pro model. The root `manager_agent` receives user queries and routes them to specialized sub-agents, such as the `ticket_management_agent`, which handles issue tracking, escalation, and resolution strategies.
   - It maintains memory and contextual sessions using Firestore (`FirestoreSessionService`) and Vertex AI RAG Memory Service.

2. **Firebase Cloud Functions (API Gateway)**:
   A set of RESTful endpoints serving as the communication layer between front-end interfaces (users, technicians) and the backend Vertex AI agents. These functions manage:
   - User logins and session management (`TriageAI_Login`).
   - Agent interaction streaming (`raise_query`, `interact`).
   - Technician operations (`technician_login`, `technician_interact`, `close_ticket`).
   - Interaction history retrieval (`get_interaction_history`).

3. **Firestore Database**:
   Used for robust, serverless state management. It stores:
   - `adk_sessions`: Reasoning engine conversational state.
   - `tickets`: The active IT service desk tickets.
   - `interactions`: Chat histories between users, agents, and technicians.
   - `Technicians`: Profiles, expertise, and operational metrics of support staff.

## 📂 Project Structure

```text
TriageAI/
├── manager_agent/              # Core Agentic Logic (Google ADK)
│   ├── adk_app.py              # Vertex AI Agent Engine application setup
│   ├── agent.py                # Definition of the root Manager Agent
│   ├── firestore/              # Custom Firestore session service integration
│   └── sub_agents/             # Specialized sub-agents (e.g., ticket_management_agent)
├── firebase_functions/         # API Gateway
│   └── functions/
│       └── main.py             # Cloud Functions definitions (CORS-enabled REST endpoints)
├── deploy.py                   # Script to deploy the manager_agent to Vertex AI
├── benchmark.py                # Benchmarking utility for testing agent latency and accuracy
├── add_technicians.py          # Seed script to populate Firestore with sample technicians
├── remote_test.py              # Utility script to test the deployed agent remotely
└── requirements.txt            # Python dependencies
```

## 🛠 Prerequisites

- Python 3.9+
- Google Cloud Project with the following APIs enabled:
  - Vertex AI API
  - Cloud Firestore API
  - Cloud Functions API
- Google Cloud SDK (`gcloud`) CLI installed and authenticated.
- Firebase CLI (`firebase-tools`) installed and authenticated.

## 🚀 Setup & Deployment

### 1. Environment Variables

Create a `.env` file in the root of the repository. You will need to define:

```env
PROJECT_ID="your-google-cloud-project-id"
LOCATION="us-central1"
REGION="us-central1"
STAGING_BUCKET="gs://your-staging-bucket-name"
DATABASE="triageai"
CUSTOM_SA_EMAIL="your-service-account-email@your-project.iam.gserviceaccount.com"
REASONING_ENGINE_ID="your-deployed-engine-id" # Updated after deployment
```

### 2. Deploy the Reasoning Agent

To package and deploy the `manager_agent` to Google Cloud Vertex AI Agent Engines, run:

```bash
python deploy.py
```

This script will automatically package the agent code, resolve credentials via impersonation (if configured), and create or update the Reasoning Engine in Vertex AI. Take note of the created `REASONING_ENGINE_ID` and update your `.env` and `firebase_functions/functions/main.py` files accordingly.

### 3. Seed Firestore Database

Initialize your Firestore database (`triageai`) with dummy technician data to ensure the system can assign tickets:

```bash
python add_technicians.py
```

### 4. Deploy Firebase Functions

Navigate to the Firebase functions directory, install dependencies, and deploy:

```bash
cd firebase_functions/functions
pip install -r requirements.txt
firebase deploy --only functions
```

## 🧪 Testing and Benchmarking

TriageAI includes built-in scripts to evaluate the performance of your deployed reasoning engine.

- **Remote Test (`remote_test.py`)**: A simple script to simulate a user session and interact with the deployed Vertex AI Reasoning Engine.
  ```bash
  python remote_test.py
  ```

- **Benchmarking (`benchmark.py`)**: Tests the agent against predefined IT queries, evaluating accuracy, latency, words per second, and characters per second. It generates Matplotlib charts summarizing the performance.
  ```bash
  python benchmark.py
  ```

## 📄 License

See the [LICENSE](LICENSE) file for details.
