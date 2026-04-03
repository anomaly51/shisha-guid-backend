FROM python:3.11-slim

WORKDIR /code

ENV POETRY_VERSION=1.7.1
ENV POETRY_VIRTUALENVS_CREATE=false

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

COPY pyproject.toml poetry.lock* ./

ARG INSTALL_DEV=true
RUN if [ "$INSTALL_DEV" = "true" ]; then poetry install --no-root; else poetry install --only main --no-root; fi

COPY ./app /code/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]