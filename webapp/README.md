# BioAgent Web Application

A stunning, research-grade web interface for AI-powered bioinformatics analysis. Built with FastAPI, Next.js, and real-time streaming.

## Architecture

```
Frontend (Next.js 14)    Backend (FastAPI)    BioAgent Core
        |                      |                   |
   React Chat UI  <--SSE-->  REST API  <------>  72+ Tools
   File Browser              Auth                 6 Specialists
   Visualizations            Rate Limiting        Multi-Agent
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Anthropic API Key ([get one here](https://console.anthropic.com/))

### 1. Configure Environment

```bash
cd webapp
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 2. Start Services

```bash
# Linux/macOS
chmod +x setup.sh
./setup.sh

# Or with Docker Compose directly
docker compose up -d
```

### 3. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001

## Security Features

This implementation includes comprehensive security measures:

### Backend Security

- **Rate Limiting**: Configurable per-IP rate limiting (default: 60 req/min)
- **Security Headers**: X-Frame-Options, CSP, HSTS, XSS protection
- **Input Validation**: Pydantic schemas with strict validation
- **File Type Validation**: Whitelist of allowed bioinformatics file extensions
- **Path Traversal Protection**: Sanitized filenames and paths
- **CORS Protection**: Configurable allowed origins
- **Request Logging**: Structured logging with audit trail
- **Error Handling**: Generic error messages (no internal details exposed)

### Authentication (Ready for Integration)

- Clerk authentication support (optional)
- API key validation for external access
- JWT token support ready

### Data Protection

- File uploads stored in isolated user directories
- Database credentials from environment variables
- No secrets in code or logs

## Project Structure

```
webapp/
├── backend/                 # FastAPI backend
│   ├── main.py             # Application entry point
│   ├── routers/            # API route handlers
│   │   ├── chat.py         # Chat & messaging endpoints
│   │   ├── files.py        # File upload/download
│   │   └── analyses.py     # Analysis management
│   ├── services/           # Business logic
│   │   ├── agent_service.py # BioAgent integration
│   │   └── streaming.py    # SSE streaming service
│   ├── models/             # Database models & schemas
│   │   ├── database.py     # SQLAlchemy models
│   │   └── schemas.py      # Pydantic schemas
│   └── middleware/         # Security middleware
│       ├── security.py     # Rate limiting, headers
│       └── logging.py      # Request logging
│
├── frontend/               # Next.js frontend
│   ├── app/               # App Router (Next.js 14)
│   │   ├── page.tsx       # Dashboard home page
│   │   └── chat/          # Chat interface
│   ├── components/        # React components
│   │   └── ui/           # Reusable UI components
│   ├── lib/              # Utilities & API client
│   └── styles/           # Global styles
│
├── docker-compose.yml     # Complete development stack
├── .env.example          # Environment template
└── setup.sh              # Setup script
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | **Required** - Your Anthropic API key | - |
| `DATABASE_URL` | PostgreSQL connection string | Docker default |
| `REDIS_URL` | Redis connection string | Docker default |
| `ALLOWED_ORIGINS` | CORS allowed origins | localhost:3000 |
| `RATE_LIMIT_PER_MINUTE` | Rate limit per IP | 60 |
| `MAX_FILE_SIZE_MB` | Max upload size | 500 |

### Production Deployment

For production:

1. Set `ENVIRONMENT=production`
2. Configure `ALLOWED_ORIGINS` to your domain
3. Generate a secure `SECRET_KEY`
4. Use managed PostgreSQL and Redis
5. Configure SSL/TLS
6. Set up authentication (Clerk recommended)

## API Endpoints

### Chat

- `POST /api/chat/sessions` - Create session
- `GET /api/chat/sessions` - List sessions
- `GET /api/chat/sessions/{id}` - Get session
- `POST /api/chat/sessions/{id}/messages` - Send message (SSE stream)
- `DELETE /api/chat/sessions/{id}` - Delete session

### Files

- `POST /api/files/upload` - Upload file
- `GET /api/files/list` - List files
- `GET /api/files/download/{user_id}/{filename}` - Download file
- `GET /api/files/preview/{filename}` - Preview file
- `DELETE /api/files/delete/{filename}` - Delete file

### Analyses

- `POST /api/analyses` - Create analysis
- `GET /api/analyses` - List analyses
- `GET /api/analyses/{id}` - Get analysis
- `PATCH /api/analyses/{id}/status` - Update status
- `DELETE /api/analyses/{id}` - Delete analysis
- `GET /api/analyses/stats/summary` - Get statistics

## Development

### Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

## Useful Commands

```bash
# View logs
docker compose logs -f

# Stop services
docker compose down

# Restart services
docker compose restart

# Full reset (removes data!)
docker compose down -v && docker compose up -d --build
```

## License

MIT License - see LICENSE file for details.
