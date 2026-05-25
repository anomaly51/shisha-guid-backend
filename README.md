# 💨 ShishaGuid Backend API

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-00a393.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-316192.svg)
![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg)

A robust and asynchronous Backend API for the ShishaGuid application, built with **FastAPI** and **PostgreSQL**. This service handles user authentication via Google OAuth2, secure session management using JWT, and provides a fully interactive Swagger UI for testing.

---

## ✨ Features

* **Modern Stack:** Built on FastAPI for high performance and automatic interactive API documentation.
* **Google OAuth2 Integration:** Secure login flow with PKCE support natively integrated into the Swagger UI.
* **Asynchronous Database:** Non-blocking database operations using `SQLAlchemy 2.0` and `asyncpg`.
* **JWT Security:** Stateless session management with JSON Web Tokens.
* **Containerized:** Fully reproducible local development environment using Docker and Docker Compose.

---

## 🛠️ Tech Stack

* **Framework:** FastAPI
* **Database:** PostgreSQL
* **ORM:** SQLAlchemy (Async)
* **Migrations:** Alembic *(planned)*
* **Authentication:** Google OAuth2, PyJWT
* **Containerization:** Docker, Docker Compose

---

## 🚀 Local Development (Quick Start)

Local Docker development uses the same PostgreSQL instance as the workload-1
deployment. The database is reached through a local `kubectl port-forward`; the
compose stack no longer starts a disposable PostgreSQL container.

### 1. Prerequisites
Make sure you have [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running on your machine.

### 2. Environment Setup
Generate a local `.env` file from the Kubernetes secret:

```bash
./scripts/remote-db-env.sh
```

The generated `.env` is ignored by git and points Docker Compose to
`host.docker.internal:15432`.

### 3. Start the database tunnel

Keep this command running in a separate terminal:

```bash
./scripts/remote-db-port-forward.sh
```

### 4. Build and Run

Start the application and local MinIO using Docker Compose:

```bash
docker-compose up --build -d
```

The API will be available at http://localhost:8000.

### 5. API Documentation & Testing

FastAPI automatically generates interactive API documentation.

Open your browser and go to http://localhost:8000/docs.

Click the green Authorize button at the top right.

Leave the client_secret field empty and click Authorize to log in via your Google Account.

You can now test protected endpoints (e.g., /api/v1/users/me).

### 6. Stopping the Environment

To stop the containers:

```bash
docker-compose down
```

The database is remote, so `docker-compose down -v` only removes local MinIO
data, not PostgreSQL data in workload-1.

📁 Project Structure
Plaintext
├── app/
│   ├── api/          # API routers (v1)
│   ├── core/         # Core config, security, and database setup
│   ├── models/       # SQLAlchemy database models
│   └── main.py       # FastAPI application instance
├── docker-compose.yml
├── Dockerfile
├── requirements.txt / pyproject.toml
└── README.md
