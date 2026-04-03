# ShishaGuid Backend

Backend API for the ShishaGuid project.

## Local Development

We use a pure Docker environment. No local Python or virtual environments are required.

### Steps to run:

1. Build and start the container:
   ```bash
   docker-compose up --build

2. Open your browser and access the Swagger UI:
http://localhost:8000/docs

3. To stop the server, press Ctrl+C in your terminal, or run:
docker-compose down