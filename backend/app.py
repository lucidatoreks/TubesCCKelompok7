from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from pymongo import MongoClient
from datetime import datetime
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://micro-example.info"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Define Prometheus metrics
REQUEST_COUNT = Counter(
    'request_count_total',
    'Total number of requests by endpoint and method',
    ['endpoint', 'method', 'status']
)

REQUEST_LATENCY = Histogram(
    'request_latency_seconds',
    'Request latency in seconds by endpoint and method',
    ['endpoint', 'method']
)

MESSAGE_COUNT = Counter(
    'message_count_total',
    'Total number of messages sent',
    ['source']
)

# Connect to MongoDB
client = MongoClient('mongodb://mongodb-service:27017/')
db = client['chat_db']
messages_collection = db['messages']

@app.route('/metrics', methods=['GET'])
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.route('/api/messages', methods=['GET'])
@REQUEST_LATENCY.labels(endpoint='/api/messages', method='GET').time()
def get_messages():
    try:
        messages = list(messages_collection.find({}, {'_id': 0}).sort('timestamp', 1))
        REQUEST_COUNT.labels(endpoint='/api/messages', method='GET', status='success').inc()
        return jsonify(messages)
    except Exception as e:
        REQUEST_COUNT.labels(endpoint='/api/messages', method='GET', status='error').inc()
        logger.error(f"Error retrieving messages: {str(e)}")
        return jsonify([]), 500

@app.route('/api/messages', methods=['POST'])
@REQUEST_LATENCY.labels(endpoint='/api/messages', method='POST').time()
def send_message():
    try:
        data = request.json
        if not data or 'text' not in data or 'from' not in data:
            REQUEST_COUNT.labels(endpoint='/api/messages', method='POST', status='error').inc()
            return jsonify({'error': 'Missing required fields'}), 400

        message = {
            'text': data['text'],
            'from': data['from'],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        messages_collection.insert_one(message)
        message.pop('_id', None)
        
        # Increment message counter by source
        MESSAGE_COUNT.labels(source=data['from']).inc()
        REQUEST_COUNT.labels(endpoint='/api/messages', method='POST', status='success').inc()
        
        return jsonify(message), 201
    except Exception as e:
        REQUEST_COUNT.labels(endpoint='/api/messages', method='POST', status='error').inc()
        logger.error(f"Error sending message: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)