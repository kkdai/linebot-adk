# LINE Bot with OpenAI Agent and Google Gemini

## Project Background

This project is a LINE bot that uses both OpenAI Agent functionality and Google Gemini models to generate responses to text inputs. The bot can answer questions in Traditional Chinese and provide helpful information.

## Screenshot

![image](https://github.com/user-attachments/assets/61066eef-2802-4967-a5eb-e2a4e430e5f7)


## Features

- Text message processing using OpenAI Agent in Traditional Chinese
- Support for function calling with tools like weather information and translation
- Integration with LINE Messaging API for easy mobile access
- Built with FastAPI for efficient asynchronous processing

## Technologies Used

- Python 3
- FastAPI
- LINE Messaging API
- OpenAI Agent framework
- Aiohttp
- PIL (Python Imaging Library)

## Setup

1. Clone the repository to your local machine.
2. Set the following environment variables:
   - `ChannelSecret`: Your LINE channel secret
   - `ChannelAccessToken`: Your LINE channel access token
   - `EXAMPLE_BASE_URL`: Your OpenAI compatible API base URL. If you want to use Google Gemini, you should fill `https://generativelanguage.googleapis.com/v1beta/` here.
   - `EXAMPLE_API_KEY`: Your OpenAI compatible API key, If you want to use Gemini
   - `EXAMPLE_MODEL_NAME`: The model name to use with the API (e.g., "gpt-4")

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

Send any text message to the LINE bot, and it will use the OpenAI Agent to generate a response in Traditional Chinese.

### Available Tools

The bot has access to the following function tools:

- `get_weather`: Get weather information for a specified city
- `translate_to_chinese`: Translate text to Traditional Chinese

## Deployment Options

### Local Development

Use ngrok or similar tools to expose your local server to the internet for webhook access:

```
ngrok http 8000
```

### Docker Deployment

You can use the included Dockerfile to build and deploy the application:

```
docker build -t linebot-openai-agent .
docker run -p 8000:8000 -e ChannelSecret=YOUR_SECRET -e ChannelAccessToken=YOUR_TOKEN -e EXAMPLE_BASE_URL=YOUR_BASE_URL -e EXAMPLE_API_KEY=YOUR_API_KEY -e EXAMPLE_MODEL_NAME=YOUR_MODEL linebot-openai-agent
```

### Cloud Deployment

1. Install the Google Cloud SDK and authenticate with your Google Cloud account.
2. Build the Docker image:

   ```
   gcloud builds submit --tag gcr.io/$GOOGLE_PROJECT_ID/linebot-openai-agent
   ```

3. Deploy the Docker image to Cloud Run:

   ```
   gcloud run deploy linebot-openai-agent --image gcr.io/$GOOGLE_PROJECT_ID/linebot-openai-agent --platform managed --region $REGION --allow-unauthenticated
   ```

4. Set up your LINE bot webhook URL to point to the Cloud Run service URL.
