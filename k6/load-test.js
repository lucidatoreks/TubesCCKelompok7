import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const requestDuration = new Trend('request_duration');

export const options = {
  stages: [
    { duration: '30s', target: 5 },   // Ramp up to 5 users
    { duration: '1m', target: 5 },    // Stay at 5 users for 1 minute
    { duration: '30s', target: 10 },  // Ramp up to 10 users
    { duration: '1m', target: 10 },   // Stay at 10 users for 1 minute
    { duration: '30s', target: 0 },   // Ramp down to 0 users
  ],
  thresholds: {
    errors: ['rate<0.1'],  // error rate should be less than 10%
    request_duration: ['p(95)<500'],  // 95% of requests should be below 500ms
    http_req_duration: ['p(95)<500'], // 95% of requests should complete below 500ms
  },
};

export default function () {
  const baseUrl = 'http://micro-example.info';
 
  // Test home page (root path)
  const rootRes = http.get(`${baseUrl}/`);
  check(rootRes, {
    'home page status is 200': (r) => r.status === 200,
    'home page contains expected content': (r) => r.body.includes('Home Chat'),
  }) || errorRate.add(1);
  requestDuration.add(rootRes.timings.duration);

  // Test room chat page
  const roomRes = http.get(`${baseUrl}/room`);
  check(roomRes, {
    'room page status is 200': (r) => r.status === 200,
    'room page contains expected content': (r) => r.body.includes('Room Chat'),
  }) || errorRate.add(1);
  requestDuration.add(roomRes.timings.duration);

  // Test GET messages API
  const getRes = http.get(`${baseUrl}/api/messages`);
  check(getRes, {
    'GET messages status is 200': (r) => r.status === 200,
    'GET messages returns valid JSON': (r) => {
      try {
        JSON.parse(r.body);
        return true;
      } catch {
        return false;
      }
    },
  }) || errorRate.add(1);
  requestDuration.add(getRes.timings.duration);

  // Test POST message API
  const payload = JSON.stringify({
    from: 'load-tester',
    text: `Test message ${new Date().toISOString()}`
  });
  
  const headers = { 
    'Content-Type': 'application/json',
    'Origin': 'http://micro-example.info'
  };
  
  const postRes = http.post(`${baseUrl}/api/messages`, payload, {
    headers: headers,
  });
  
  // Debug log to see actual response
  if (__ITER === 0) {
    console.log('First POST response:', postRes.body);
  }
  
  check(postRes, {
    'POST message status is 201': (r) => r.status === 201,
    'POST response is valid': (r) => {
      try {
        const json = JSON.parse(r.body);
        // Updated validation to match actual API response format
        return json.from && json.text && typeof json.from === 'string' && typeof json.text === 'string';
      } catch (e) {
        console.error('JSON parse error:', e);
        return false;
      }
    },
  }) || errorRate.add(1);
  requestDuration.add(postRes.timings.duration);

  sleep(1);
}