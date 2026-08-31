# 🛡️ PR-Agent: AI Code Summarizer

> Stop wasting 15 minutes deciphering what a PR does. Let AI do the heavy lifting.

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.2-green.svg)](https://fastapi.tiangolo.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-purple.svg)](https://openai.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📸 Demo

![PR-Agent Demo](assets/demo.gif)

**Before:** A messy PR with 15 files changed and vague description  
**After:** A clean 3-bullet summary with labels, review time, and suggestions

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (optional)
- OpenAI API Key
- GitHub Personal Access Token

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/mefaisalraheem/pr-agent.git

cd pr-agent



    Copy environment variables



cp .env.example .env

    Edit .env with your credentials



OPENAI_API_KEY=sk-...
GITHUB_TOKEN=ghp_...
GITHUB_WEBHOOK_SECRET=your_secret

    Run with Docker Compose (recommended)



docker-compose up -d

    Or run locally



pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8000

🔧 Configuration

Environment Variables
Variable	Description	Default
OPENAI_API_KEY	Your OpenAI API key	Required
OPENAI_MODEL	OpenAI model to use	gpt-4-turbo-preview
OPENAI_TEMPERATURE	Response randomness (0.0-1.0)	0.3
GITHUB_TOKEN	GitHub Personal Access Token	Required
GITHUB_WEBHOOK_SECRET	Webhook secret for verification	Required
REDIS_URL	Redis connection URL	redis://redis:6379/0
EXCLUDE_FILE_PATTERNS	Files to exclude from analysis	package-lock.json,*.min.js,...

🎯 Features

    ✅ 3-Bullet Summary - Concise overview of PR changes

    ✅ Breaking Change Detection - Identify breaking changes automatically

    ✅ Review Time Estimation - Estimate how long the review will take

    ✅ Reviewer Suggestions - Suggest reviewers based on code areas

    ✅ Smart Labeling - Auto-label PRs (bugfix, feature, enhancement, etc.)

    ✅ Redis Caching - Cache results to avoid re-analyzing

    ✅ Rate Limiting - Protect against abuse

    ✅ Error Handling - Graceful failure with retry logic

    ✅ Production Ready - Docker, logging, health checks, and more


  




    
🧪 Testing




Run the test suite with coverage:


# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_diff_parser.py -v


📈 Performance

Metric	Value
Average Response Time	2-5 seconds
OpenAI Token Usage	~200-400 tokens/PR
Cost per PR	~$0.005 - $0.01
Cache Hit Rate	~70% (with Redis)
Time Saved per PR	10-15 minutes

💰 Economics

This bot processes ~50 PRs per month for an average team.

    Total OpenAI Cost: ~$5/month

    Time Saved: ~10 hours/week

    ROI: Priceless 🚀

🐛 Troubleshooting

Common Issues

1. Webhook signature verification fails

    Ensure GITHUB_WEBHOOK_SECRET matches the one configured in GitHub

    Check that the secret is set in both GitHub webhook settings and .env

2. Redis connection fails

    Verify Redis is running: docker-compose ps redis

    Check REDIS_URL in .env

3. OpenAI API rate limits

    Increase OPENAI_TEMPERATURE slightly

    Check your OpenAI account usage

🤝 Contributing

    Fork the repository

    Create a feature branch

    Make your changes

    Add tests

    Submit a pull request

📝 License

MIT License - see LICENSE file for details


🙏 Acknowledgments

    Built with FastAPI

    Powered by OpenAI

    Inspired by the need to save time on code reviews


    Made with ❤️ by the Malik Faisal Raheem


🚀 Deployment Commands

 


# Clone and setup
git clone https://github.com/mefaisalraheem/pr-agent.git
cd pr-agent

# Build and run with Docker
docker-compose up -d --build

# Check logs
docker-compose logs -f app

# Run tests
docker-compose exec app pytest tests/ -v

# Stop everything
docker-compose down



🔒 Security Checklist

    ☑

    Environment variables (not hardcoded)
    ☑

    Webhook signature verification
    ☑

    Rate limiting
    ☑

    Non-root user in Docker
    ☑

    Input validation (Pydantic)
    ☑

    Error handling (no sensitive data exposure)
    ☑

    HTTPS only (in production)
    ☑

    Logging (no sensitive data)


📊 Monitoring Commands


# Check health
curl http://localhost:8000/health

# View logs
docker-compose logs -f app

# Check Redis status
docker-compose exec redis redis-cli ping

# Clear Redis cache
docker-compose exec redis redis-cli FLUSHALL






````markdown
## 🔄 How It Works

```mermaid
flowchart TD
    A[Developer Opens PR] --> B[GitHub Webhook]
    B --> C[FastAPI Endpoint]
    C --> D[Verify Signature]
    D --> E[Check Cache]

    E -->|Cache Miss| F[Fetch PR Diff]
    F --> G[Smart Filtering]
    G --> H[OpenAI Analysis]
    H --> I[Cache Result]
    I --> J[Post Comment + Labels]

    E -->|Cache Hit| J
