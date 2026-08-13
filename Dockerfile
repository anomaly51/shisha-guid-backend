FROM python:3.11-slim

WORKDIR /code

ENV POETRY_VIRTUALENVS_CREATE=false

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock* ./

RUN poetry lock

ARG INSTALL_DEV=true
RUN if [ "$INSTALL_DEV" = "true" ]; then poetry install --no-root; else poetry install --only main --no-root; fi

COPY ./app /code/app
COPY ./alembic /code/alembic
COPY ./alembic.ini /code/alembic.ini

ARG APP_VERSION
ARG BUILD_DATE
ARG VCS_REF
ENV APP_VERSION=$APP_VERSION
ENV BUILD_DATE=$BUILD_DATE
ENV VCS_REF=$VCS_REF
RUN printf '%s\n' "$BUILD_DATE" > /code/.build-date

CMD ["sh", "-c", "python -m app.db_bootstrap && alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
