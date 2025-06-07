# YouTube Transcript Chat

An interactive application that lets you converse with YouTube content by processing video transcripts through Google's Gemini AI.

## Overview

This application allows you to:

- Chat with an AI about YouTube video content
- Process both individual videos and playlists
- Analyze transcripts from YouTube videos
- Get AI-generated insights and explanations about video content

## Features

- **YouTube Content Processing**: Extract metadata and transcripts from YouTube videos and playlists
- **AI-Powered Conversations**: Interact with video content using Google's Gemini AI
- **Database Caching**: Store processed videos for faster retrieval on subsequent requests
- **Two Application Modes**:
  - Chat Interface: Converse with AI about video content
  - XML Converter: Extract and view structured video data

## How It Works

1. **Content Detection**: The app scans your messages for YouTube links using regex pattern matching
2. **Content Processing**:
   - Extracts video transcripts using the `youtube-transcript-api`
   - Retrieves metadata (title, channel, description) via HTTP requests
   - Stores data in a PostgreSQL database (Neon) for future retrieval
   - Formats content in a structured way for the AI model
3. **AI Interaction**: The Gemini AI uses the video content as context to answer your questions

## Getting Started

### Prerequisites

- Python 3.9 or higher
- An internet connection
- A Google Gemini API key
- (Optional) A Neon PostgreSQL database connection string

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Youtube-LLM
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install required dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   
   Create a `.env` file in the project root with:
   ```
   GEMINI_API_KEY=your_gemini_api_key
   NEON_YOUTUBE_DATABASE_URL=your_neon_database_url  # Optional
   ```

### Usage

#### Chat Application (Main Interface)
```bash
streamlit run src/streamlit_app.py
```

#### Video Data Extraction Tool
```bash
streamlit run src/app.py
```