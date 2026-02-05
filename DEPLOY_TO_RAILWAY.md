# Deploying pharmEZ to Railway

Railway is a cloud platform that is very easy to use and often has less strict network restrictions than Render's free tier.

## Prerequisites
1.  **GitHub Account**: Your code must be pushed to a GitHub repository.
2.  **Railway Account**: Sign up at [railway.app](https://railway.app/).
3.  **MongoDB Atlas**: Your database is hosted on MongoDB Atlas (which you already have).

## Step-by-Step Deployment Guide

### 1. Login and Create Project
1.  Go to your [Railway Dashboard](https://railway.app/dashboard).
2.  Click **"New Project"**.
3.  Select **"Deploy from GitHub repo"**.
4.  If prompted, authorize Railway to access your GitHub account.
5.  Search for and select your **pharmEZ** repository (`vishalgangisetty/newPEZ`).

### 2. Configure Service
1.  Railway will automatically detect that it's a Python app.
2.  Click **"Deploy Now"** (or "Add Variables" first if the option is there). 
    *   *Note*: The first build might fail or the app might crash if variables aren't set yet. That's normal.

### 3. Add Environment Variables
Once the project is created (even if building), go to the **"Variables"** tab of your service. Add the following variables (copy values from your local `.env` file):

| Variable Key | Value (Example/Description) |
| :--- | :--- |
| `FLASK_SECRET_KEY` | `pharmEZ_secret_key_2026` (or generate a new random string) |
| `MONGO_URI` | `mongodb+srv://vishal123:Vishal123@cluster0.kkmfpkn.mongodb.net/?appName=Cluster0` |
| `GOOGLE_API_KEY` | Your Google Gemini API Key |
| `PINECONE_API_KEY` | Your Pinecone API Key |
| `EMAIL_SENDER` | `pharmeez@gmail.com` |
| `EMAIL_PASSWORD` | Your 16-character Google App Password |
| `PORT` | `8080` (Optional, Railway assigns one automatically, but good to have) |

### 4. Verify Deployment
1.  Go to the **"Settings"** tab -> **"Networking"**.
2.  Click **"Generate Domain"** to get a public URL (e.g., `pharmEZ-production.up.railway.app`).
3.  Click the URL to open your app.

### 5. Troubleshooting Email
If you still face issues with email sending on Railway:
1.  Go to the **"Logs"** tab in Railway to see real-time error messages.
2.  Railway generally allows outbound SMTP on port 587, so the current configuration should work.

## Notes on File Storage
Like Render, Railway's filesystem is **ephemeral**.
*   Uploaded prescriptions (`data/input`) will disappear if the app restarts or redeploys.
*   For a production app, you would typically use an external storage service like **AWS S3** or **Cloudinary**.
*   However, since we are storing the *text content* of prescriptions in Pinecone/MongoDB, the core functionality (chat, reminders) will still work even if the original PDF/Image file is deleted from the server.
