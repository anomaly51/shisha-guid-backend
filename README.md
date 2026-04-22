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

We use a pure Docker environment. No local Python installation or virtual environments are required.

### 1. Prerequisites
Make sure you have [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running on your machine.

### 2. Environment Setup
Create a `.env` file in the root directory of the project. You must configure your database credentials and Google OAuth2 keys (contact the repository owner for the staging keys if you don't have them):

```env
# Database Settings
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/shishadb

# Security
SECRET_KEY=your-super-secret-jwt-key

# Google OAuth2 Credentials
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
3. Build and Run
Start the application and the database using Docker Compose:

Bash
docker-compose up --build -d
The API will be available at http://localhost:8000.

4. API Documentation & Testing
FastAPI automatically generates interactive API documentation.

Open your browser and go to http://localhost:8000/docs.

Click the green Authorize button at the top right.

Leave the client_secret field empty and click Authorize to log in via your Google Account.

You can now test protected endpoints (e.g., /api/v1/users/me).

5. Stopping the Environment
To stop the containers:

Bash
docker-compose down
Note: If you need to completely wipe the local database and start fresh, use the -v flag: docker-compose down -v.

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