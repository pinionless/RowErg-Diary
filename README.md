# RowErg Diary 🚣‍♂️

RowErg Diary is a self-hosted web application designed for rowing enthusiasts to track, analyze, and visualize their workout data. It provides a centralized platform to import workout files from services like Technogym's MyWellness or to enter them manually, offering detailed insights into performance metrics, long-term progress, and personal rankings.

## ✨ Key Features

*   **Multiple Data Entry Methods:** Import workout data from MyWellness JSON files or use the intuitive form for manual entries.
*   **Interactive Performance Charts:** Visualize your pace, power, stroke rate (SPM), and heart rate for each workout with zoomable, interactive charts.
*   **In-Depth Analytics:** Get detailed 500m split breakdowns and see how much time you spent in each configurable heart rate zone.
*   **Personal Ranking System:** See how your workouts rank against each other overall, by year, and by month to track your improvement.
*   **Historical Summaries:** View aggregated workout data by day, week, month, or year to see the bigger picture.


 ## Getting Your MyWellness JSON Data

To import your SKILLROW workouts, you'll need the JSON data from your MyWellness account.

1.  **Use the Helper Script:** We recommend using this Greasemonkey/Tampermonkey script to easily obtain the JSON link:
    *   [RowErg JSON Helper Script](https://github.com/pinionless/rowerg-json-helper/blob/main/rowerg-json-helper.user.js)
2.  **Copy & Paste:** Once you have the JSON content, copy it and paste it into the designated textarea in the RowErg Diary application.

*   **Dockerized & Easy to Deploy:** The entire application is containerized, allowing for a simple and consistent setup process.

## 🛠️ Tech Stack

*   **Backend:** Python with Flask
*   **Database:** PostgreSQL
*   **ORM:** SQLAlchemy
*   **Frontend:** HTML, CSS, JavaScript, ApexCharts.js
*   **Containerization:** Docker & Docker Compose

## ✅ Prerequisites

To run this project locally, you will need the following tools installed:

*   [Docker](https://docs.docker.com/engine/install/)
*   [Docker Compose](https://docs.docker.com/compose/install/)

## 🚀 Local Development Setup

Follow these steps to get your local development environment up and running.

**1. Clone the Repository**
```bash
git clone https://github.com/pinionless/rowergdiary.git
cd rowergdiary
```

**2. Configure and Run the Application**
The project uses Docker Compose to manage all services. You can use the official pre-built image for a quick start.

Create a `docker-compose.yml` file in the project root with the following content:

```yaml
services:
  rowergdiary:
    image: ghcr.io/pinionless/rowerg-diary:latest
    container_name: rowerg_diary
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      FLASK_APP: app.py
      FLASK_ENV: development
      POSTGRES_USER: myuser
      POSTGRES_PASSWORD: mypassword
      POSTGRES_DB: mydatabase
      POSTGRES_HOST: rowerg_diary_db
    depends_on:
      rowerg_diary_db:
        condition: service_healthy

  rowerg_diary_db:
    image: postgres:17-alpine
    container_name: rowerg_diary_db
    restart: unless-stopped
    volumes:
      - postgres_data:/var/lib/postgresql/data/
    environment:
      POSTGRES_USER: myuser
      POSTGRES_PASSWORD: mypassword
      POSTGRES_DB: mydatabase
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

Then, start the services:
```bash
docker-compose up -d
```




## 🤝 Contributing

Contributions are welcome! Please feel free to open an issue to discuss a bug or feature, or submit a pull request with your improvements. For major changes, please open an issue first to discuss what you would like to change.
