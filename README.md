# Strava Telegram Bot 🏃

Auto-analyzes your Strava activities with Gemini AI and sends results to Telegram.

## Setup

### Environment Variables (set in Render dashboard)
| Variable | Value |
|---|---|
| `TELEGRAM_TOKEN` | Your Telegram bot token |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |
| `STRAVA_CLIENT_ID` | Strava app client ID |
| `STRAVA_CLIENT_SECRET` | Strava app client secret |
| `STRAVA_VERIFY_TOKEN` | Any random string (e.g. `myverifytoken123`) |
| `GEMINI_API_KEY` | Google Gemini API key |

### After deploying to Render:
1. Go to `https://your-app.onrender.com/auth`
2. Authorize Strava
3. Register webhook (see README)
