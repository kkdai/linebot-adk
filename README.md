# LINE Bot with OpenAI Agent and Google Gemini

## Project Background

This project is a LINE bot that uses both OpenAI Agent functionality and Google Gemini models to generate responses to text inputs. The bot can answer questions in Traditional Chinese and provide helpful information.

## Screenshot

![image](https://github.com/user-attachments/assets/2bcbd827-0047-4a3a-8645-f8075d996c10)


## Features

- Text message processing using AI models (OpenAI or Google Gemini)
- Support for function calling with custom tools
- Integration with LINE Messaging API
- Built with FastAPI for high-performance async processing
- Containerized with Docker for easy deployment

## Technologies Used

- Python 3.9+
- FastAPI
- LINE Messaging API
- OpenAI API / Google Gemini API
- Docker
- Google Cloud Run (for deployment)

## Setup

1. Clone the repository to your local machine.
2. Set the following environment variables:
   - `ChannelSecret`: Your LINE channel secret
   - `ChannelAccessToken`: Your LINE channel access token
   - `GEMINI_API_KEY`: Your Google Gemini API key (if using Gemini)

3. Install the required dependencies:

   ```
   pip install -r requirements.txt
   ```

4. Start the FastAPI server:

   ```
   uvicorn main:app --reload
   ```

5. Set up your LINE bot webhook URL to point to your server's endpoint.

## Usage

### Text Processing

Send any text message to the LINE bot, and it will use the configured AI model to generate a response. The bot is optimized for Traditional Chinese responses.

### Available Tools

The bot can be configured with various function tools such as:

- Weather information retrieval
- Translation services
- Data lookup capabilities
- Custom tools based on your specific needs

## Deployment Options

### Local Development

Use ngrok or similar tools to expose your local server to the internet for webhook access:

```
ngrok http 8000
```

### Docker Deployment

You can use the included Dockerfile to build and deploy the application:

```
docker build -t linebot-ai .
docker run -p 8000:8000 \
  -e ChannelSecret=YOUR_SECRET \
  -e ChannelAccessToken=YOUR_TOKEN \
  -e GEMINI_API_KEY=YOUR_GEMINI_KEY \
  linebot-ai
```

### Google Cloud Deployment

#### Prerequisites

1. Install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
2. Create a Google Cloud project and enable the following APIs:
   - Cloud Run API
   - Container Registry API or Artifact Registry API
   - Cloud Build API

#### Steps for Deployment

1. Authenticate with Google Cloud:

   ```
   gcloud auth login
   ```

2. Set your Google Cloud project:

   ```
   gcloud config set project YOUR_PROJECT_ID
   ```

3. Build and push the Docker image to Google Container Registry:

   ```
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/linebot-ai
   ```

4. Deploy to Cloud Run:

   ```
   gcloud run deploy linebot-ai \
     --image gcr.io/YOUR_PROJECT_ID/linebot-ai \
     --platform managed \
     --region asia-east1 \
     --allow-unauthenticated \
     --set-env-vars ChannelSecret=YOUR_SECRET,ChannelAccessToken=YOUR_TOKEN,GEMINI_API_KEY=YOUR_GEMINI_KEY
   ```

   Note: For production, it's recommended to use Secret Manager for storing sensitive environment variables.

5. Get the service URL:

   ```
   gcloud run services describe linebot-ai --platform managed --region asia-east1 --format 'value(status.url)'
   ```

6. Set the service URL as your LINE Bot webhook URL in the LINE Developer Console.

#### Setting Up Secrets in Google Cloud (Recommended)

For better security, store your API keys as secrets:

1. Create secrets for your sensitive values:

   ```
   echo -n "YOUR_SECRET" | gcloud secrets create line-channel-secret --data-file=-
   echo -n "YOUR_TOKEN" | gcloud secrets create line-channel-token --data-file=-
   echo -n "YOUR_OPENAI_KEY" | gcloud secrets create openai-api-key --data-file=-
   echo -n "YOUR_GEMINI_KEY" | gcloud secrets create gemini-api-key --data-file=-
   ```

2. Give the Cloud Run service access to these secrets:

   ```
   gcloud secrets add-iam-policy-binding line-channel-secret --member=serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com --role=roles/secretmanager.secretAccessor
   gcloud secrets add-iam-policy-binding line-channel-token --member=serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com --role=roles/secretmanager.secretAccessor
   gcloud secrets add-iam-policy-binding openai-api-key --member=serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com --role=roles/secretmanager.secretAccessor
   gcloud secrets add-iam-policy-binding gemini-api-key --member=serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com --role=roles/secretmanager.secretAccessor
   ```

3. Deploy with secrets:

   ```
   gcloud run deploy linebot-ai \
     --image gcr.io/YOUR_PROJECT_ID/linebot-ai \
     --platform managed \
     --region asia-east1 \
     --allow-unauthenticated \
     --set-env-vars MODEL_PROVIDER=openai,MODEL_NAME=gpt-4 \
     --update-secrets=ChannelSecret=line-channel-secret:latest,ChannelAccessToken=line-channel-token:latest,OPENAI_API_KEY=openai-api-key:latest,GEMINI_API_KEY=gemini-api-key:latest
   ```

## Maintenance and Monitoring

After deployment, you can monitor your service through the Google Cloud Console:

1. View logs: `gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=linebot-ai"`
2. Check service metrics: Access the Cloud Run dashboard in Google Cloud Console
3. Set up alerts for error rates or high latency in Cloud Monitoring
