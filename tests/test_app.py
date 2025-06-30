"""
Test cases for KIU Meeting Intelligence System
"""
import pytest
import os
import tempfile
import json
import sqlite3
from unittest.mock import patch, MagicMock
import sys

# Add the parent directory to the path to import the app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, init_database
from config import TestingConfig

@pytest.fixture
def client():
    """Create a test client"""
    app.config.from_object(TestingConfig)
    
    with app.test_client() as client:
        with app.app_context():
            init_database()
            yield client

@pytest.fixture
def mock_openai():
    """Mock OpenAI API responses"""
    with patch('openai.audio.transcriptions.create') as mock_transcribe, \
         patch('openai.chat.completions.create') as mock_chat, \
         patch('openai.embeddings.create') as mock_embeddings, \
         patch('openai.images.generate') as mock_images:
        
        # Mock Whisper transcription
        mock_transcribe.return_value = MagicMock(
            text="This is a test meeting transcript.",
            duration=1800  # 30 minutes
        )
        
        # Mock GPT-4 chat completion
        mock_chat.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content="This is a comprehensive meeting summary.",
                    function_call=None
                )
            )]
        )
        
        # Mock embeddings
        mock_embeddings.return_value = MagicMock(
            data=[MagicMock(embedding=[0.1] * 1536)]
        )
        
        # Mock DALL-E image generation
        mock_images.return_value = MagicMock(
            data=[MagicMock(url="https://example.com/test-image.png")]
        )
        
        yield {
            'transcribe': mock_transcribe,
            'chat': mock_chat,
            'embeddings': mock_embeddings,
            'images': mock_images
        }

class TestBasicRoutes:
    """Test basic application routes"""
    
    def test_index_page(self, client):
        """Test the main index page loads correctly"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'KIU Meeting Intelligence' in response.data
    
    def test_meetings_endpoint_empty(self, client):
        """Test meetings endpoint returns empty list initially"""
        response = client.get('/meetings')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_analytics_endpoint(self, client):
        """Test analytics endpoint returns correct structure"""
        response = client.get('/analytics')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'total_meetings' in data
        assert 'average_duration_minutes' in data
        assert 'searchable_chunks' in data
        assert 'apis_integrated' in data

class TestFileUpload:
    """Test file upload functionality"""
    
    def test_upload_no_file(self, client):
        """Test upload without file returns error"""
        response = client.post('/upload-meeting', data={
            'title': 'Test Meeting',
            'attendees': 'John Doe'
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_upload_invalid_file_type(self, client):
        """Test upload with invalid file type"""
        with tempfile.NamedTemporaryFile(suffix='.txt') as temp_file:
            temp_file.write(b'This is not an audio file')
            temp_file.seek(0)
            
            response = client.post('/upload-meeting', data={
                'title': 'Test Meeting',
                'attendees': 'John Doe',
                'audio_file': (temp_file, 'test.txt')
            })
            assert response.status_code == 400
    
    @patch('requests.get')
    def test_upload_valid_file(self, mock_requests, client, mock_openai):
        """Test successful file upload and processing"""
        # Mock the image download request
        mock_requests.return_value.content = b'fake image data'
        
        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
            temp_file.write(b'fake audio data')
            temp_file.seek(0)
            
            response = client.post('/upload-meeting', data={
                'title': 'Test Meeting',
                'attendees': 'John Doe, Jane Smith',
                'audio_file': (temp_file, 'test.mp3')
            })
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'meeting_id' in data

class TestMeetingData:
    """Test meeting data operations"""
    
    @patch('requests.get')
    def test_meeting_creation_and_retrieval(self, mock_requests, client, mock_openai):
        """Test creating and retrieving a meeting"""
        # Mock the image download
        mock_requests.return_value.content = b'fake image data'
        
        # Create a meeting
        with tempfile.NamedTemporaryFile(suffix='.wav') as temp_file:
            temp_file.write(b'fake audio data')
            temp_file.seek(0)
            
            upload_response = client.post('/upload-meeting', data={
                'title': 'Strategy Meeting',
                'attendees': 'Alice, Bob, Charlie',
                'audio_file': (temp_file, 'strategy.wav')
            })
            
            assert upload_response.status_code == 200
            upload_data = json.loads(upload_response.data)
            meeting_id = upload_data['meeting_id']
            
            # Retrieve the meeting
            detail_response = client.get(f'/meeting/{meeting_id}')
            assert detail_response.status_code == 200
            
            detail_data = json.loads(detail_response.data)
            assert detail_data['title'] == 'Strategy Meeting'
            assert detail_data['attendees'] == 'Alice, Bob, Charlie'
            assert 'transcription' in detail_data
            assert 'summary' in detail_data
    
    def test_meeting_not_found(self, client):
        """Test retrieving non-existent meeting"""
        response = client.get('/meeting/999')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

class TestSemanticSearch:
    """Test semantic search functionality"""
    
    def test_search_no_query(self, client):
        """Test search without query returns error"""
        response = client.post('/search', json={})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_search_empty_results(self, client, mock_openai):
        """Test search with no matching results"""
        response = client.post('/search', json={'query': 'nonexistent topic'})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
    
    @patch('requests.get')
    def test_search_with_results(self, mock_requests, client, mock_openai):
        """Test search returning results"""
        # Mock the image download
        mock_requests.return_value.content = b'fake image data'
        
        # First create a meeting
        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
            temp_file.write(b'fake audio data')
            temp_file.seek(0)
            
            client.post('/upload-meeting', data={
                'title': 'Product Launch Meeting',
                'attendees': 'Product Team',
                'audio_file': (temp_file, 'product.mp3')
            })
        
        # Now search for it
        response = client.post('/search', json={'query': 'product launch'})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)

class TestFineTuning:
    """Test fine-tuning functionality"""
    
    @patch('requests.get')
    def test_fine_tune_data_creation(self, mock_requests, client, mock_openai):
        """Test creating fine-tuning data"""
        # Mock the image download
        mock_requests.return_value.content = b'fake image data'
        
        # Create a meeting first
        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
            temp_file.write(b'fake audio data')
            temp_file.seek(0)
            
            client.post('/upload-meeting', data={
                'title': 'Fine-tune Test Meeting',
                'attendees': 'AI Team',
                'audio_file': (temp_file, 'ai_meeting.mp3')
            })
        
        # Create fine-tuning data
        response = client.post('/fine-tune-data')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'examples_count' in data

class TestErrorHandling:
    """Test error handling scenarios"""
    
    def test_invalid_json_search(self, client):
        """Test search with invalid JSON"""
        response = client.post('/search', data='invalid json')
        assert response.status_code in [400, 415]  # Bad request or unsupported media type
    
    @patch('openai.audio.transcriptions.create')
    def test_whisper_api_failure(self, mock_transcribe, client):
        """Test handling of Whisper API failure"""
        mock_transcribe.side_effect = Exception("API Error")
        
        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
            temp_file.write(b'fake audio data')
            temp_file.seek(0)
            
            response = client.post('/upload-meeting', data={
                'title': 'Error Test Meeting',
                'attendees': 'Test User',
                'audio_file': (temp_file, 'error_test.mp3')
            })
            
            assert response.status_code == 500

class TestDatabaseIntegration:
    """Test database operations"""
    
    def test_database_initialization(self):
        """Test database tables are created correctly"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            temp_db_path = temp_db.name
        
        try:
            # Create connection and initialize
            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()
            
            # Create tables (copied from init_database function)
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
            
            # Verify tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            assert 'meetings' in tables
            assert 'meeting_embeddings' in tables
            assert 'fine_tuning_data' in tables
            
            conn.close()
        
        finally:
            # Clean up
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)

if __name__ == '__main__':
    pytest.main([__file__, '-v']) 