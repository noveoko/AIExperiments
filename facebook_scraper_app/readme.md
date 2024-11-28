# Marketplace Monitor

A web application that monitors marketplace listings for lawn equipment and trailers, analyzing potential flipping opportunities within a 60-mile radius. Built with Flask, React, and Celery.

## Features

- Real-time listing monitoring and notifications
- Profit potential analysis based on historical prices
- Category-based filtering (zero-turn mowers, push mowers, stand-on mowers, trailers)
- Distance-based filtering (60-mile radius)
- Mobile-responsive design
- WebSocket integration for instant updates

## Prerequisites

- Python 3.8+
- Node.js 14+
- Redis Server
- SQLite (for development)

## Project Structure

```
marketplace-monitor/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── routes.py
│   │   └── tasks.py
│   ├── requirements.txt
│   └── run.py
└── frontend/
    ├── public/
    ├── src/
    │   ├── components/
    │   │   └── ListingMonitor.jsx
    │   ├── App.js
    │   └── index.js
    └── package.json
```

## Installation

### Backend Setup

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install Python dependencies:
```bash
cd backend
pip install -r requirements.txt
```

3. Start Redis server:
```bash
redis-server
```

4. Initialize the database:
```bash
flask db upgrade
```

### Frontend Setup

1. Install Node.js dependencies:
```bash
cd frontend
npm install
```

## Configuration

1. Create a `.env` file in the backend directory:
```env
FLASK_APP=run.py
FLASK_ENV=development
DATABASE_URL=sqlite:///marketplace_monitor.db
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

2. Update frontend API configuration in `src/config.js` if needed.

## Running the Application

### Backend

1. Start the Flask server:
```bash
cd backend
flask run
```

2. Start Celery worker:
```bash
celery -A app.celery worker --loglevel=info
```

3. Start Celery beat (for scheduled tasks):
```bash
celery -A app.celery beat --loglevel=info
```

### Frontend

1. Start the React development server:
```bash
cd frontend
npm start
```

The application will be available at `http://localhost:3000`

## Development

### Adding New Features

1. Backend:
- Add new models to `app/models.py`
- Create new routes in `app/routes.py`
- Add Celery tasks in `app/tasks.py`

2. Frontend:
- Add new components in `src/components/`
- Update state management as needed
- Add new API calls in service files

### Testing

```bash
# Backend tests
cd backend
python -m pytest

# Frontend tests
cd frontend
npm test
```

## Deployment

1. Build the frontend:
```bash
cd frontend
npm run build
```

2. Configure your production server (nginx, gunicorn, etc.)

3. Update environment variables for production

4. Set up SSL certificates

## API Documentation

### Endpoints

- `GET /api/listings`: Get all listings
  - Query parameters:
    - `category`: Filter by category
    - `min_profit`: Minimum profit potential
    - `distance`: Maximum distance in miles

- `GET /api/categories`: Get available categories

- WebSocket events:
  - `new_listing`: Emitted when a new listing is found
  - `price_update`: Emitted when price analysis is updated

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Security Considerations

- Implement rate limiting
- Add authentication
- Sanitize user inputs
- Follow API usage guidelines
- Secure WebSocket connections

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with [Flask](https://flask.palletsprojects.com/)
- Built with [React](https://reactjs.org/)
- UI components from [shadcn/ui](https://ui.shadcn.com/)
- Icons from [Lucide](https://lucide.dev/)

## Contact

For questions and support, please open an issue in the repository.