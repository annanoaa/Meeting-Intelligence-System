from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
import openai
import os
import sqlite3
import json
import numpy as np
from datetime import datetime
import io
import base64
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import logging
from typing import List, Dict, Any

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenAI configuration
openai.api_key = os.getenv('OPENAI_API_KEY')

# File upload configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_database():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect('meetings.db')
    cursor = conn.cursor()
    
    # Meetings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date_recorded DATETIME,
            transcription TEXT,
            summary TEXT,
            action_items TEXT,
            decisions TEXT,
            attendees TEXT,
            duration_minutes INTEGER,
            audio_file_path TEXT,
            visual_summary_path TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Embeddings table for semantic search
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meeting_embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER,
            text_chunk TEXT,
            embedding BLOB,
            chunk_index INTEGER,
            FOREIGN KEY (meeting_id) REFERENCES meetings (id)
        )
    ''')
    
    # Fine-tuning data table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fine_tuning_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT,
            completion TEXT,
            meeting_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meeting_id) REFERENCES meetings (id)
        )
    ''')
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/upload-meeting', methods=['POST'])
def upload_meeting():
    """Upload and process meeting audio file"""
    try:
        if 'audio_file' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        file = request.files['audio_file']
        meeting_title = request.form.get('title', 'Untitled Meeting')
        attendees = request.form.get('attendees', '')
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Process the audio file
            meeting_id = process_meeting_audio(file_path, meeting_title, attendees)
            
            return jsonify({
                'success': True,
                'meeting_id': meeting_id,
                'message': 'Meeting uploaded and processed successfully'
            })
        
        return jsonify({'error': 'Invalid file type'}), 400
        
    except Exception as e:
        logger.error(f"Error uploading meeting: {str(e)}")
        return jsonify({'error': str(e)}), 500

def process_meeting_audio(file_path: str, title: str, attendees: str) -> int:
    """Process audio file through all AI APIs"""
    try:
        # Step 1: Transcribe audio using Whisper API
        logger.info("Starting audio transcription...")
        with open(file_path, 'rb') as audio_file:
            transcription = openai.Audio.transcribe(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json"
            )
        
        transcript_text = transcription['text']
        duration = transcription.get('duration', 0)
        
        # Step 2: Analyze content using GPT-4
        logger.info("Analyzing meeting content...")
        analysis = analyze_meeting_content(transcript_text)
        
        # Step 3: Create visual summary using DALL-E 3
        logger.info("Creating visual summary...")
        visual_summary_path = create_visual_summary(analysis['summary'], title)
        
        # Step 4: Store in database
        meeting_id = store_meeting_data(
            title, transcript_text, analysis, attendees, 
            duration, file_path, visual_summary_path
        )
        
        # Step 5: Create embeddings for semantic search
        logger.info("Creating embeddings for semantic search...")
        create_meeting_embeddings(meeting_id, transcript_text)
        
        return meeting_id
        
    except Exception as e:
        logger.error(f"Error processing meeting audio: {str(e)}")
        raise e

def analyze_meeting_content(transcript: str) -> Dict[str, Any]:
    """Analyze meeting transcript using GPT-4 with function calling"""
    
    # Define functions for GPT-4 to call
    functions = [
        {
            "name": "extract_action_items",
            "description": "Extract action items with owners and deadlines",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task": {"type": "string"},
                                "owner": {"type": "string"},
                                "deadline": {"type": "string"},
                                "priority": {"type": "string", "enum": ["High", "Medium", "Low"]}
                            }
                        }
                    }
                }
            }
        },
        {
            "name": "extract_decisions",
            "description": "Extract key decisions made during the meeting",
            "parameters": {
                "type": "object",
                "properties": {
                    "decisions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "decision": {"type": "string"},
                                "rationale": {"type": "string"},
                                "impact": {"type": "string"}
                            }
                        }
                    }
                }
            }
        }
    ]
    
    # Analyze the transcript
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": """You are an AI assistant specialized in analyzing business meeting transcripts. 
                Your task is to extract actionable insights, decisions, and create comprehensive summaries.
                Focus on identifying specific action items with clear ownership and deadlines."""
            },
            {
                "role": "user",
                "content": f"""Please analyze this meeting transcript and extract:
                1. A comprehensive summary
                2. Action items with owners and deadlines
                3. Key decisions made
                
                Transcript: {transcript}"""
            }
        ],
        functions=functions,
        function_call="auto",
        temperature=0.3
    )
    
    # Create summary
    summary_response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "You are an expert meeting summarizer. Create concise, actionable summaries."
            },
            {
                "role": "user",
                "content": f"Create a comprehensive but concise summary of this meeting: {transcript[:2000]}..."
            }
        ],
        temperature=0.3
    )
    
    analysis = {
        'summary': summary_response['choices'][0]['message']['content'],
        'action_items': [],
        'decisions': []
    }
    
    # Process function calls if any
    if response['choices'][0]['message'].get('function_call'):
        function_name = response['choices'][0]['message']['function_call']['name']
        function_args = json.loads(response['choices'][0]['message']['function_call']['arguments'])
        
        if function_name == "extract_action_items":
            analysis['action_items'] = function_args.get('action_items', [])
        elif function_name == "extract_decisions":
            analysis['decisions'] = function_args.get('decisions', [])
    
    return analysis

def create_visual_summary(summary: str, title: str) -> str:
    """Create visual summary using DALL-E 3"""
    try:
        # Create a prompt for visual summary
        visual_prompt = f"""Create a professional business infographic that represents the key points of this meeting summary: {summary[:500]}
        Style: Clean, modern, corporate infographic with icons and visual elements representing meeting outcomes, decisions, and action items.
        Include: Charts, arrows, icons for teamwork, decisions, and progress. Use a professional color scheme."""
        
        response = openai.Image.create(
            prompt=visual_prompt,
            size="1024x1024",
            n=1
        )
        
        # Download and save the image
        image_url = response['data'][0]['url']
        import requests
        img_response = requests.get(image_url)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        visual_path = f"static/visuals/{timestamp}_{secure_filename(title)}.png"
        os.makedirs(os.path.dirname(visual_path), exist_ok=True)
        
        with open(visual_path, 'wb') as f:
            f.write(img_response.content)
        
        return visual_path
        
    except Exception as e:
        logger.error(f"Error creating visual summary: {str(e)}")
        return ""

def store_meeting_data(title: str, transcript: str, analysis: Dict, attendees: str, 
                      duration: int, audio_path: str, visual_path: str) -> int:
    """Store meeting data in database"""
    conn = sqlite3.connect('meetings.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO meetings (title, transcription, summary, action_items, decisions, 
                            attendees, duration_minutes, audio_file_path, visual_summary_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        title,
        transcript,
        analysis['summary'],
        json.dumps(analysis['action_items']),
        json.dumps(analysis['decisions']),
        attendees,
        duration,
        audio_path,
        visual_path
    ))
    
    meeting_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return meeting_id

def create_meeting_embeddings(meeting_id: int, transcript: str):
    """Create embeddings for semantic search"""
    # Split transcript into chunks for better search granularity
    chunk_size = 1000
    chunks = [transcript[i:i+chunk_size] for i in range(0, len(transcript), chunk_size)]
    
    conn = sqlite3.connect('meetings.db')
    cursor = conn.cursor()
    
    for i, chunk in enumerate(chunks):
        # Create embedding using OpenAI Embeddings API
        response = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=chunk
        )
        
        embedding = response['data'][0]['embedding']
        embedding_blob = np.array(embedding).tobytes()
        
        cursor.execute('''
            INSERT INTO meeting_embeddings (meeting_id, text_chunk, embedding, chunk_index)
            VALUES (?, ?, ?, ?)
        ''', (meeting_id, chunk, embedding_blob, i))
    
    conn.commit()
    conn.close()

@app.route('/meetings', methods=['GET'])
def get_meetings():
    """Get all meetings"""
    conn = sqlite3.connect('meetings.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, title, date_recorded, summary, attendees, duration_minutes, created_at
        FROM meetings ORDER BY created_at DESC
    ''')
    
    meetings = []
    for row in cursor.fetchall():
        meetings.append({
            'id': row[0],
            'title': row[1],
            'date_recorded': row[2],
            'summary': row[3],
            'attendees': row[4],
            'duration_minutes': row[5],
            'created_at': row[6]
        })
    
    conn.close()
    return jsonify(meetings)

@app.route('/meeting/<int:meeting_id>', methods=['GET'])
def get_meeting_details(meeting_id):
    """Get detailed meeting information"""
    conn = sqlite3.connect('meetings.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM meetings WHERE id = ?
    ''', (meeting_id,))
    
    row = cursor.fetchone()
    if not row:
        return jsonify({'error': 'Meeting not found'}), 404
    
    meeting = {
        'id': row[0],
        'title': row[1],
        'date_recorded': row[2],
        'transcription': row[3],
        'summary': row[4],
        'action_items': json.loads(row[5]) if row[5] else [],
        'decisions': json.loads(row[6]) if row[6] else [],
        'attendees': row[7],
        'duration_minutes': row[8],
        'audio_file_path': row[9],
        'visual_summary_path': row[10],
        'created_at': row[11]
    }
    
    conn.close()
    return jsonify(meeting)

@app.route('/search', methods=['POST'])
def semantic_search():
    """Semantic search across all meetings"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Create embedding for search query
        response = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=query
        )
        
        query_embedding = np.array(response['data'][0]['embedding'])
        
        # Search similar chunks
        conn = sqlite3.connect('meetings.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT me.meeting_id, me.text_chunk, me.embedding, m.title, m.summary
            FROM meeting_embeddings me
            JOIN meetings m ON me.meeting_id = m.id
        ''')
        
        results = []
        for row in cursor.fetchall():
            chunk_embedding = np.frombuffer(row[2], dtype=np.float64)
            similarity = np.dot(query_embedding, chunk_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(chunk_embedding)
            )
            
            results.append({
                'meeting_id': row[0],
                'text_chunk': row[1],
                'similarity': float(similarity),
                'meeting_title': row[3],
                'meeting_summary': row[4]
            })
        
        # Sort by similarity and return top 10
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        conn.close()
        return jsonify(results[:10])
        
    except Exception as e:
        logger.error(f"Error in semantic search: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/fine-tune-data', methods=['POST'])
def create_fine_tune_data():
    """Prepare data for fine-tuning"""
    try:
        # Get all meetings for fine-tuning data preparation
        conn = sqlite3.connect('meetings.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, transcription, summary, action_items FROM meetings')
        meetings = cursor.fetchall()
        
        fine_tune_examples = []
        
        for meeting in meetings:
            meeting_id, transcript, summary, action_items = meeting
            
            # Create training examples for company-specific terminology
            examples = [
                {
                    "prompt": f"Summarize this meeting transcript: {transcript[:500]}",
                    "completion": summary
                },
                {
                    "prompt": f"Extract action items from: {transcript[:500]}",
                    "completion": action_items
                }
            ]
            
            for example in examples:
                cursor.execute('''
                    INSERT INTO fine_tuning_data (prompt, completion, meeting_id)
                    VALUES (?, ?, ?)
                ''', (example['prompt'], example['completion'], meeting_id))
                
                fine_tune_examples.append(example)
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Created {len(fine_tune_examples)} fine-tuning examples',
            'examples_count': len(fine_tune_examples)
        })
        
    except Exception as e:
        logger.error(f"Error creating fine-tune data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/analytics', methods=['GET'])
def get_analytics():
    """Get meeting analytics and insights"""
    conn = sqlite3.connect('meetings.db')
    cursor = conn.cursor()
    
    # Basic analytics
    cursor.execute('SELECT COUNT(*) FROM meetings')
    total_meetings = cursor.fetchone()[0]
    
    cursor.execute('SELECT AVG(duration_minutes) FROM meetings WHERE duration_minutes > 0')
    avg_duration = cursor.fetchone()[0] or 0
    
    cursor.execute('''
        SELECT COUNT(*) FROM meeting_embeddings me
        JOIN meetings m ON me.meeting_id = m.id
    ''')
    total_searchable_chunks = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total_meetings': total_meetings,
        'average_duration_minutes': round(avg_duration, 2),
        'searchable_chunks': total_searchable_chunks,
        'apis_integrated': ['Whisper', 'GPT-4', 'Embeddings', 'DALL-E 3']
    })

if __name__ == '__main__':
    init_database()
    app.run(debug=True, port=5000) 