// KIU Meeting Intelligence System - Frontend JavaScript

// Global variables
let currentMeetings = [];
let isLoading = false;

// DOM Ready
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    setupEventListeners();
    loadMeetings();
    loadAnalytics();
    
    // Add enter key support for search
    document.getElementById('searchQuery').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            performSearch();
        }
    });
}

function setupEventListeners() {
    // Upload form submission
    document.getElementById('uploadForm').addEventListener('submit', handleFileUpload);
    
    // Navigation smooth scrolling
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// Utility function for smooth scrolling
function scrollToSection(sectionId) {
    const element = document.getElementById(sectionId);
    if (element) {
        element.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }
}

// File Upload Handler
async function handleFileUpload(event) {
    event.preventDefault();
    
    if (isLoading) return;
    
    const form = event.target;
    const formData = new FormData(form);
    const uploadBtn = document.getElementById('uploadBtn');
    const progressContainer = document.getElementById('uploadProgress');
    const progressBar = progressContainer.querySelector('.progress-bar');
    const progressText = document.getElementById('progressText');
    
    // Validate file
    const fileInput = document.getElementById('audioFile');
    const file = fileInput.files[0];
    
    if (!file) {
        showAlert('Please select an audio file.', 'warning');
        return;
    }
    
    // Check file size (100MB limit)
    if (file.size > 100 * 1024 * 1024) {
        showAlert('File size must be less than 100MB.', 'error');
        return;
    }
    
    // Check file type
    const allowedTypes = ['audio/mp3', 'audio/wav', 'audio/x-m4a', 'audio/mp4'];
    if (!allowedTypes.includes(file.type) && !file.name.match(/\.(mp3|wav|m4a)$/i)) {
        showAlert('Please select a valid audio file (MP3, WAV, or M4A).', 'error');
        return;
    }
    
    try {
        isLoading = true;
        
        // Update UI
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';
        progressContainer.style.display = 'block';
        
        // Simulate progress updates
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += Math.random() * 15;
            if (progress > 90) progress = 90;
            
            progressBar.style.width = progress + '%';
            
            if (progress < 30) {
                progressText.textContent = 'Uploading audio file...';
            } else if (progress < 60) {
                progressText.textContent = 'Transcribing with Whisper API...';
            } else if (progress < 80) {
                progressText.textContent = 'Analyzing content with GPT-4...';
            } else {
                progressText.textContent = 'Creating visual summary...';
            }
        }, 1000);
        
        // Upload file
        const response = await fetch('/upload-meeting', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        clearInterval(progressInterval);
        progressBar.style.width = '100%';
        progressText.textContent = 'Processing complete!';
        
        if (response.ok && result.success) {
            showAlert('Meeting processed successfully!', 'success');
            
            // Reset form
            form.reset();
            progressContainer.style.display = 'none';
            
            // Reload meetings and analytics
            await loadMeetings();
            await loadAnalytics();
            
            // Scroll to meetings section
            setTimeout(() => {
                scrollToSection('meetings');
            }, 1000);
            
        } else {
            throw new Error(result.error || 'Upload failed');
        }
        
    } catch (error) {
        console.error('Upload error:', error);
        showAlert('Error processing meeting: ' + error.message, 'error');
        progressContainer.style.display = 'none';
    } finally {
        isLoading = false;
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = '<i class="fas fa-upload me-2"></i>Process Meeting';
    }
}

// Load Meetings
async function loadMeetings() {
    try {
        const response = await fetch('/meetings');
        const meetings = await response.json();
        
        currentMeetings = meetings;
        displayMeetings(meetings);
        
    } catch (error) {
        console.error('Error loading meetings:', error);
        showAlert('Error loading meetings', 'error');
    }
}

// Display Meetings
function displayMeetings(meetings) {
    const container = document.getElementById('meetingsList');
    
    if (meetings.length === 0) {
        container.innerHTML = `
            <div class="col-12">
                <div class="text-center py-5">
                    <i class="fas fa-calendar-times fa-3x text-muted mb-3"></i>
                    <h4 class="text-muted">No meetings yet</h4>
                    <p class="text-muted">Upload your first meeting recording to get started!</p>
                    <button class="btn btn-primary" onclick="scrollToSection('upload')">
                        <i class="fas fa-upload me-2"></i>Upload Meeting
                    </button>
                </div>
            </div>
        `;
        return;
    }
    
    container.innerHTML = meetings.map(meeting => `
        <div class="col-lg-6 col-md-12">
            <div class="meeting-card">
                <h5 class="meeting-title">${escapeHtml(meeting.title)}</h5>
                <div class="meeting-meta">
                    <i class="fas fa-calendar me-2"></i>
                    ${formatDate(meeting.created_at)}
                    ${meeting.duration_minutes ? `<span class="ms-3"><i class="fas fa-clock me-1"></i>${meeting.duration_minutes} min</span>` : ''}
                    ${meeting.attendees ? `<span class="ms-3"><i class="fas fa-users me-1"></i>${meeting.attendees}</span>` : ''}
                </div>
                <div class="meeting-summary">
                    ${meeting.summary ? truncateText(meeting.summary, 150) : 'Processing...'}
                </div>
                <div class="meeting-actions">
                    <button class="btn btn-primary btn-sm" onclick="showMeetingDetails(${meeting.id})">
                        <i class="fas fa-eye me-1"></i>View Details
                    </button>
                    <button class="btn btn-outline-secondary btn-sm" onclick="searchSimilarMeetings('${escapeHtml(meeting.title)}')">
                        <i class="fas fa-search me-1"></i>Find Similar
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

// Show Meeting Details Modal
async function showMeetingDetails(meetingId) {
    try {
        const response = await fetch(`/meeting/${meetingId}`);
        const meeting = await response.json();
        
        if (!response.ok) {
            throw new Error(meeting.error || 'Failed to load meeting details');
        }
        
        // Update modal content
        document.getElementById('meetingModalTitle').textContent = meeting.title;
        document.getElementById('meetingModalBody').innerHTML = `
            <div class="row">
                <div class="col-md-8">
                    <h6><i class="fas fa-file-alt me-2"></i>Summary</h6>
                    <p class="mb-4">${meeting.summary || 'No summary available'}</p>
                    
                    ${meeting.action_items && meeting.action_items.length > 0 ? `
                        <h6><i class="fas fa-tasks me-2"></i>Action Items</h6>
                        <div class="mb-4">
                            ${meeting.action_items.map(item => `
                                <div class="action-item priority-${item.priority ? item.priority.toLowerCase() : 'medium'}">
                                    <h6>${escapeHtml(item.task)}</h6>
                                    <div class="row">
                                        <div class="col-sm-6">
                                            <strong>Owner:</strong> ${escapeHtml(item.owner || 'Unassigned')}
                                        </div>
                                        <div class="col-sm-6">
                                            <strong>Deadline:</strong> ${escapeHtml(item.deadline || 'Not specified')}
                                        </div>
                                    </div>
                                    ${item.priority ? `<span class="badge bg-${getPriorityColor(item.priority)} mt-2">${item.priority} Priority</span>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                    
                    ${meeting.decisions && meeting.decisions.length > 0 ? `
                        <h6><i class="fas fa-check-circle me-2"></i>Key Decisions</h6>
                        <div class="mb-4">
                            ${meeting.decisions.map(decision => `
                                <div class="decision-item">
                                    <h6>${escapeHtml(decision.decision)}</h6>
                                    ${decision.rationale ? `<p><strong>Rationale:</strong> ${escapeHtml(decision.rationale)}</p>` : ''}
                                    ${decision.impact ? `<p><strong>Impact:</strong> ${escapeHtml(decision.impact)}</p>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                    
                    <h6><i class="fas fa-microphone me-2"></i>Full Transcript</h6>
                    <div class="transcript-text">
                        ${meeting.transcription || 'Transcript not available'}
                    </div>
                </div>
                <div class="col-md-4">
                    ${meeting.visual_summary_path ? `
                        <h6><i class="fas fa-image me-2"></i>Visual Summary</h6>
                        <img src="${meeting.visual_summary_path}" alt="Visual Summary" class="visual-summary img-fluid">
                    ` : ''}
                    
                    <h6 class="mt-4"><i class="fas fa-info-circle me-2"></i>Meeting Info</h6>
                    <ul class="list-unstyled">
                        <li><strong>Date:</strong> ${formatDate(meeting.created_at)}</li>
                        ${meeting.duration_minutes ? `<li><strong>Duration:</strong> ${meeting.duration_minutes} minutes</li>` : ''}
                        ${meeting.attendees ? `<li><strong>Attendees:</strong> ${escapeHtml(meeting.attendees)}</li>` : ''}
                    </ul>
                </div>
            </div>
        `;
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('meetingModal'));
        modal.show();
        
    } catch (error) {
        console.error('Error loading meeting details:', error);
        showAlert('Error loading meeting details: ' + error.message, 'error');
    }
}

// Semantic Search
async function performSearch() {
    const query = document.getElementById('searchQuery').value.trim();
    
    if (!query) {
        showAlert('Please enter a search query', 'warning');
        return;
    }
    
    const resultsContainer = document.getElementById('searchResults');
    resultsContainer.innerHTML = `
        <div class="text-center py-3">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Searching...</span>
            </div>
            <div class="mt-2">Searching across all meetings...</div>
        </div>
    `;
    
    try {
        const response = await fetch('/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query })
        });
        
        const results = await response.json();
        
        if (!response.ok) {
            throw new Error(results.error || 'Search failed');
        }
        
        displaySearchResults(results, query);
        
    } catch (error) {
        console.error('Search error:', error);
        resultsContainer.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                Search failed: ${error.message}
            </div>
        `;
    }
}

// Display Search Results
function displaySearchResults(results, query) {
    const container = document.getElementById('searchResults');
    
    if (results.length === 0) {
        container.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle me-2"></i>
                No results found for "${escapeHtml(query)}". Try different keywords.
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <div class="mb-3">
            <h5>Search Results (${results.length})</h5>
            <small class="text-muted">Results for: "${escapeHtml(query)}"</small>
        </div>
        ${results.map(result => `
            <div class="search-result">
                <div class="search-result-title">
                    ${escapeHtml(result.meeting_title)}
                    <span class="similarity-score">${Math.round(result.similarity * 100)}% match</span>
                </div>
                <div class="search-result-excerpt">
                    ${highlightQuery(result.text_chunk, query, 200)}
                </div>
                <div class="mt-2">
                    <button class="btn btn-sm btn-outline-primary" onclick="showMeetingDetails(${result.meeting_id})">
                        <i class="fas fa-eye me-1"></i>View Meeting
                    </button>
                </div>
            </div>
        `).join('')}
    `;
}

// Search Similar Meetings
function searchSimilarMeetings(title) {
    document.getElementById('searchQuery').value = title;
    scrollToSection('search');
    setTimeout(() => {
        performSearch();
    }, 500);
}

// Load Analytics
async function loadAnalytics() {
    try {
        const response = await fetch('/analytics');
        const analytics = await response.json();
        
        displayAnalytics(analytics);
        
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

// Display Analytics
function displayAnalytics(analytics) {
    const container = document.getElementById('analyticsCards');
    
    container.innerHTML = `
        <div class="col-lg-3 col-md-6">
            <div class="analytics-card">
                <i class="fas fa-calendar analytics-icon"></i>
                <div class="analytics-value">${analytics.total_meetings}</div>
                <div class="analytics-label">Total Meetings</div>
            </div>
        </div>
        <div class="col-lg-3 col-md-6">
            <div class="analytics-card">
                <i class="fas fa-clock analytics-icon"></i>
                <div class="analytics-value">${analytics.average_duration_minutes}</div>
                <div class="analytics-label">Avg Duration (min)</div>
            </div>
        </div>
        <div class="col-lg-3 col-md-6">
            <div class="analytics-card">
                <i class="fas fa-search analytics-icon"></i>
                <div class="analytics-value">${analytics.searchable_chunks}</div>
                <div class="analytics-label">Searchable Chunks</div>
            </div>
        </div>
        <div class="col-lg-3 col-md-6">
            <div class="analytics-card">
                <i class="fas fa-brain analytics-icon"></i>
                <div class="analytics-value">${analytics.apis_integrated.length}</div>
                <div class="analytics-label">AI APIs Integrated</div>
            </div>
        </div>
    `;
}

// Utility Functions
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function truncateText(text, maxLength) {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
}

function getPriorityColor(priority) {
    switch (priority.toLowerCase()) {
        case 'high': return 'danger';
        case 'medium': return 'warning';
        case 'low': return 'success';
        default: return 'secondary';
    }
}

function highlightQuery(text, query, maxLength = 200) {
    if (!text || !query) return escapeHtml(text.substring(0, maxLength));
    
    const lowerText = text.toLowerCase();
    const lowerQuery = query.toLowerCase();
    const index = lowerText.indexOf(lowerQuery);
    
    if (index === -1) {
        return escapeHtml(text.substring(0, maxLength)) + (text.length > maxLength ? '...' : '');
    }
    
    const start = Math.max(0, index - 50);
    const end = Math.min(text.length, start + maxLength);
    const excerpt = text.substring(start, end);
    
    const highlighted = excerpt.replace(
        new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'),
        match => `<mark>${match}</mark>`
    );
    
    return (start > 0 ? '...' : '') + highlighted + (end < text.length ? '...' : '');
}

function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alertContainer');
    const alertId = 'alert-' + Date.now();
    
    const alertHtml = `
        <div id="${alertId}" class="alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show" role="alert">
            <i class="fas fa-${getAlertIcon(type)} me-2"></i>
            ${escapeHtml(message)}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    alertContainer.insertAdjacentHTML('beforeend', alertHtml);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const alert = document.getElementById(alertId);
        if (alert) {
            const bsAlert = bootstrap.Alert.getInstance(alert);
            if (bsAlert) bsAlert.close();
        }
    }, 5000);
}

function getAlertIcon(type) {
    switch (type) {
        case 'success': return 'check-circle';
        case 'error': return 'exclamation-triangle';
        case 'warning': return 'exclamation-triangle';
        case 'info': return 'info-circle';
        default: return 'info-circle';
    }
} 