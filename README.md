# RowErg Diary 🚣‍♂️

Tracking and analyzing SKILLROW RowErg an Concept2 (or similar cardio equipment) workouts. This application allows you to import workout data, view summaries, track progress, and manage your workout history.

---

## ⚠️ **Status: Early Development** ⚠️

This project is currently in its **early development stages**. Please be aware that:
    
    ❗ Active Development Notice: Expect breaking changes to features, APIs, and the database schema; backward compatibility is not guaranteed at this early stage.
*   Functionality may be incomplete or change significantly.
*   You might encounter bugs or instability.
*   We appreciate your understanding and any feedback you might have!

---

## Current Features

*   **Import SKILLROW Workouts:** Easily upload and parse your MyWellness JSON data.
*   **Track Your Progress:** View a detailed list of all workouts with key stats.
*   **Dive Deep into Details:** Analyze individual workouts with comprehensive metrics, samples, and heart rate zone data.
*   **Daily Performance Summaries:** Get aggregated totals for each day's rowing activity.
*   **Overall Statistics:** See your lifetime rowing achievements at a glance in the sidebar.
*   **Efficient Data Handling:** Leverages materialized views for fast display of summaries and stats.
*   **Dockerized & Developer Ready:** Easy to set up and contribute.
---

## Getting Your MyWellness JSON Data

To import your SKILLROW workouts, you'll need the JSON data from your MyWellness account.

1.  **Use the Helper Script:** We recommend using this Greasemonkey/Tampermonkey script to easily obtain the JSON link:
    *   [RowErg JSON Helper Script](https://github.com/pinionless/rowerg-json-helper/blob/main/rowerg-json-helper.user.js)
2.  **Copy & Paste:** Once you have the JSON content, copy it and paste it into the designated textarea in the RowErg Diary application.

---

## Project Roadmap

We have exciting plans for RowErg Diary! You can view our detailed development roadmap here:

➡️ **[View Project Roadmap](roadmap.md)**

---

## AI WARNING

> I do not code a lot, That's why most of the foundational code and this README were created with the assistance of AI. I am actively refining and building upon this base.

---

## RowErg Diary

A Flask-based web application for tracking and analyzing SKILLROW RowErg (or similar cardio equipment) workouts. This application allows you to import workout data, view summaries, track progress, and manage your workout history.

---

## ✨ Key Features

*   **Workout Data Import:**
    *   Seamlessly import detailed SKILLROW workout data via MyWellness JSON exports.
    *   Automatic parsing of workout metrics, samples, heart rate data, and HR zones.
*   **Comprehensive Workout Diary:**
    *   Paginated list of all your workouts (`/workouts`).
    *   At-a-glance summaries for each workout (Date, Name, Distance, Duration, Average Split).
*   **Detailed Workout View (`/details/<id>`):**
    *   In-depth information for individual workouts.
    *   General workout information (ID, equipment, target, totals).
    *   List of all metric descriptors used in the workout (e.g., Pace, Power, Stroke Rate).
    *   Display of workout samples (first & last 10, with total count).
    *   Display of heart rate samples (first & last 10, with total count).
    *   Visualization of time spent in different heart rate zones.
*   **Daily Summaries (`/dailysummary`):**
    *   Paginated view of aggregated daily totals (Total Distance, Total Duration, Average Split for each day).
    *   Ability to click through to see all workouts for a specific day (`/workouts/date/<date>`).
*   **Dynamic Sidebar Statistics:**
    *   Always-visible overall lifetime statistics (Total Meters Rowed, Total Duration, Overall Average Split).
    *   Data is efficiently sourced from materialized views for quick display.
*   **Robust Database Backend:**
    *   Utilizes PostgreSQL for reliable data storage.
    *   SQLAlchemy ORM for Pythonic database interaction.
    *   Materialized views for pre-calculated aggregate statistics, ensuring fast dashboard/summary loading.
    *   Automatic refresh of materialized views upon new workout data insertion, update, or deletion via database triggers.
*   **Flexible Configuration:**
    *   App settings (like items per page, secret key) configurable via environment variables.
*   **Developer-Friendly:**
    *   Modular Flask application structure (views, models, utils).
    *   Dockerized environment for easy setup and consistent development/deployment (`docker-compose.yml` provided).
    *   Database management scripts for easy creation and deletion of all DB components (tables, MVs, functions, triggers) during development.
*   **(Planned/In Progress)** Manual workout entry form.

---

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

Before you begin, ensure you have the following installed on your system:

*   **Docker & Docker Compose:** For running the application in containers.
    *   [Install Docker Engine](https://docs.docker.com/engine/install/)
    *   [Install Docker Compose](https://docs.docker.com/compose/install/)

### Installation and Setup

  1.  **Prepare `docker-compose.yml`:**
  * See example below.

  2.  **First-Time Database Setup (Crucial!):**
  *   Open your web browser and navigate to:
      `http://localhost:5000/database/create`
  *   This will trigger the database creation script within the application, setting up necessary tables, materialized views, and triggers. You should see a success message.

### Usage

Once the application is running and the database is initialized:

*   Open your web browser and go to `http://localhost:5000`.


### docker-compose.yml
```
services:
  rowergdiary:
    image: ghcr.io/pinionless/rowerg-diary:latest
    container_name: rowerg_diary
    restart: unless-stopped
    networks:
      - rowerg_diary
    ports:
      - "5000:5000"
    environment:      
      FLASK_APP: app.py
      FLASK_ENV: development
      FLASK_DEBUG: 1
      PER_PAGE: ${PER_PAGE:-20}

      POSTGRES_USER: myuser
      POSTGRES_PASSWORD: mypassword
      POSTGRES_DB: mydatabase
      POSTGRES_HOST: rowerg_diary_db
    depends_on:
      rowerg_diary_db:
        condition: service_healthy # Waits for postgres_dev to be healthy

  rowerg_diary_db:
    image: postgres:17-alpine
    container_name: rowerg_diary_db
    restart: unless-stopped
    networks:
      - rowerg_diary
    ports:
      - "5432:5432" # Expose PostgreSQL port for local debugging (optional)
    volumes:
      - postgres_data:/var/lib/postgresql/data/ # Persistent volume for database data
    environment:
      POSTGRES_USER: myuser
      POSTGRES_PASSWORD: mypassword
      POSTGRES_DB: mydatabase
    healthcheck: # Added healthcheck for postgres
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 10s
      timeout: 5s
      retries: 5

networks:
  rowerg_diary:
    driver: bridge

volumes:
  postgres_data: # Define the named volume for PostgreSQL data persistence