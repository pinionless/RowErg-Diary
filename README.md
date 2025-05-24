# **⚠️ EARLY DEVELOPMENT ⚠️**

This project is currently in its early development stages. Functionality may be incomplete, unstable, or subject to significant changes.
### This readme, just like most of the code was written by AI.

---
# RowErg Diary

A Flask-based web application for tracking and analyzing SKILLROW RowErg (or similar cardio equipment) workouts. This application allows you to import workout data, view summaries, track progress, and manage your workout history.

## Features

*   **Workout Listing:** Browse all your recorded workouts with pagination.
*   **Workout Summaries:** Quick overview of key metrics like Duration, Distance, and Split for each workout.
*   **Detailed Workout View (Planned):** View comprehensive data for individual workouts, including samples and heart rate zones.
*   **Data Import:** Functionality to submit workout data (e.g., via JSON uploads).
*   **Database Management:** Tools for initial database setup and potential administration.
*   **Sidebar Statistics:** Always-visible aggregated rowing statistics (total meters, total time, average split).
*   **Dockerized Environment:** Easy setup and consistent development/deployment using Docker.

## Technologies Used

*   **Backend:** Flask (Python)
*   **Database:** PostgreSQL
*   **ORM:** SQLAlchemy with Flask-SQLAlchemy
*   **Containerization:** Docker, Docker Compose
*   **Frontend:** HTML, CSS (using a templating engine like Jinja2)
*   **Client-side:** jQuery, Font Awesome
*   **AI Used:** Fully build with Gemini 2.5 Pro Preview 05-06

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

Before you begin, ensure you have the following installed on your system:

*   **Git:** For cloning the repository.
*   **Docker & Docker Compose:** For running the application in containers.
    *   [Install Docker Engine](https://docs.docker.com/engine/install/)
    *   [Install Docker Compose](https://docs.docker.com/compose/install/)

### Installation and Setup

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/pinionless/RowErg-Diary.git # Replace with your actual repo URL
    cd your-repo-name # Navigate into the project directory
    ```

2.  **Environment Variables (Optional for Development, Recommended for Production):**

    For local development, `FLASK_SECRET_KEY` defaults to a generic value. For production or if you prefer explicit control, create a `.env` file in the root of your project:

    ```bash
    # .env (example for production/explicit setup)
    FLASK_SECRET_KEY=a_very_long_and_random_secret_key_here
    # You can also override PER_PAGE here if you want it different from docker-compose.yml
    # PER_PAGE=15
    ```
    *Note: The database connection details (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_HOST) are already configured within the `docker-compose.yml` file for convenience in development.*

3.  **Build and Run the Docker Containers:**

    From the root of your project directory (where `docker-compose.yml` is located), run:

    ```bash
    docker-compose up --build
    ```
    *   `--build`: This flag tells Docker Compose to rebuild the `flask_app_dev` image. It's essential the first time you run the application or after making changes to your `Dockerfile` or `requirements.txt`.
    *   This command will download the PostgreSQL image, build your Flask app image, and start both services. It might take a few minutes on the first run.

4.  **First-Time Database Setup (Crucial!)**

    After the containers are up and running, the PostgreSQL database will be empty. You need to create the necessary tables and initial data (if any) by running a specific endpoint in your application.

    *   Wait until you see output in your terminal indicating that the Flask application is running (e.g., `* Running on http://0.0.0.0:5000 (Press CTRL+C to quit)`).
    *   Open your web browser and navigate to:
        `http://localhost:5000/database/create`

    *   This will trigger the database creation script defined in your `database_management`.
    *   There is also `http://localhost:5000/database/delete` that will delete all for development only.

### Usage

Once the application is running and the database is initialized:

*   Open your web browser and go to `http://localhost:5000`.
*   You will see the home page.
*   Navigate to `/workouts` to view your workout diary (initially empty until you import data).
*   Explore other available routes as they are implemented.


### docker-compose.yml
```
# docker-compose.yml
version: '3.8' # Specify Docker Compose file format version

services:
  flask_app_dev:
    build: ./flask_app_dev         # Path to the Dockerfile for the web app
    networks:
      - dev_net
    ports:
      - "5000:5000"      # Map host port 5000 to container port 5000
    volumes:
      - ./flask_app_dev:/usr/src/app # Mount your app directory to the container
    environment:
      FLASK_APP: app.py
      FLASK_ENV: development # Enables debug mode and reloader for Flask
      FLASK_DEBUG: 1
      PER_PAGE: 20           # Number of items per page for pagination

      POSTGRES_USER: myuser
      POSTGRES_PASSWORD: mypassword
      POSTGRES_DB: mydatabase
      POSTGRES_HOST: postgres_dev # Matches the service name of the PostgreSQL container
    depends_on:
      - postgres_dev # Ensures postgres_dev starts before flask_app_dev

  postgres_dev:
    image: postgres:17-alpine
    restart: unless-stopped # Automatically restart if it crashes
    networks:
      - dev_net
    ports:
      - "5432:5432" # Expose PostgreSQL port (optional for internal use, but good for local debugging)
    volumes:
      - postgres_data:/var/lib/postgresql/data/ # Persistent volume for database data
    environment:
      POSTGRES_USER: myuser
      POSTGRES_PASSWORD: mypassword
      POSTGRES_DB: mydatabase
      POSTGRES_HOST: postgres_dev # This is typically not used by Postgres itself, but Flask app might look for it
      # Note: POSTGRES_HOST is not usually needed by the postgres container itself,
      # but it's fine to keep if your app expects it here.
      # The important connection detail for the Flask app is POSTGRES_HOST.
      # For the database container, it's just 'postgres_dev' (itself) by default within its network.


networks:
  dev_net: # Define the custom network
    driver: bridge

volumes:
  postgres_data: # Define the named volume for PostgreSQL data persistence
