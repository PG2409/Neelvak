import http from 'k6/http';
import { check, sleep } from 'k6';

/*
 * ============================================================================
 * Neelvak AIOS k6 Load Testing Script
 * ============================================================================
 * 
 * INSTALLATION INSTRUCTIONS:
 * --------------------------
 * k6 is a modern load testing tool built in Go. You must install it on your 
 * host machine to execute this script.
 * 
 * Windows (using Winget):
 *   winget install k6
 * 
 * Windows (using Chocolatey):
 *   choco install k6
 * 
 * MacOS (using Homebrew):
 *   brew install k6
 * 
 * Linux (Debian/Ubuntu):
 *   sudo gpg -k
 *   sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
 *   echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
 *   sudo apt-get update
 *   sudo apt-get install k6
 * 
 * 
 * EXECUTION INSTRUCTIONS:
 * -----------------------
 * From your terminal, run the following command to begin the load test:
 *   k6 run load_test.js
 * 
 * Make sure your Neelvak AIOS FastAPI server is already running on port 8000!
 */

export const options = {
    // 1. WORKLOAD PROFILE STAGES
    stages: [
        { duration: '15s', target: 20 }, // Warm-up phase: Ramp up from 1 to 20 VUs
        { duration: '30s', target: 20 }, // Steady state: Maintain 20 VUs for 30 seconds
        { duration: '10s', target: 0 },  // Cooldown phase: Ramp down to 0 VUs
    ],

    // 2. PERFORMANCE SLA THRESHOLDS
    thresholds: {
        // Enforce less than 1% error rate on HTTP requests
        http_req_failed: ['rate<0.01'], 
        
        // Enforce 95th percentile response time is under 2.0 seconds
        http_req_duration: ['p(95)<2000'], 
    },
};

export default function () {
    // 3. SCENARIO FUNCTIONALITY
    
    const url = 'http://127.0.0.1:8000/api/chat';
    
    // The payload passing standard query tokens as requested
    const payload = JSON.stringify({
        text: 'Analyze the structural tradeoffs of Monolithic and Microkernel operating systems.',
        prompt: 'Analyze the structural tradeoffs of Monolithic and Microkernel operating systems.' // Added to ensure compatibility with backend schema
    });

    const params = {
        headers: {
            'Content-Type': 'application/json',
        },
    };

    // Dispatch a secure HTTP POST request to the local ASGI framework
    const res = http.post(url, payload, params);

    // Verify that the return status code is exactly 200 and the response has a body
    check(res, {
        'status is 200': (r) => r.status === 200,
        'response contains data': (r) => r.body && r.body.length > 0,
    });

    // Randomized sleep/think-time delay between 0.5 and 1.5 seconds per virtual user
    // (Math.random() generates 0-1. Multiplied by 1.0 = 0-1.0. Plus 0.5 = 0.5-1.5)
    sleep(Math.random() * 1.0 + 0.5);
}
