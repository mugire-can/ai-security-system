import express, { Express, NextFunction, Request, Response } from 'express';
import cors from 'cors';
import helmet from 'helmet';
import axios from 'axios';
import dotenv from 'dotenv';
import crypto from 'crypto';

dotenv.config();

const app: Express = express();
const PORT = process.env.API_PORT || 3000;
const TRUST_PROXY = parseInt(process.env.TRUST_PROXY || '0', 10);
const API_AUTH_ENABLED = process.env.API_AUTH_ENABLED === 'true';
const API_KEYS = new Set(
  (process.env.API_KEYS || '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean)
);
const CORS_ORIGIN = process.env.CORS_ORIGIN || '*';

app.use(helmet());
if (TRUST_PROXY > 0) {
  app.set('trust proxy', TRUST_PROXY);
}

app.use(cors({
  origin: CORS_ORIGIN === '*'
    ? true
    : CORS_ORIGIN.split(',').map((value) => value.trim()).filter(Boolean),
}));
app.use(express.json());

interface Alert {
  camera_id: string;
  zone: string;
  alert_type: string;
  severity: string;
  description: string;
}

interface CameraStatus {
  camera_id: string;
  source: string;
  alive: boolean;
  last_seen: string;
}

const ALERT_DISPATCHER_URL = process.env.ALERT_DISPATCHER_URL || 'http://localhost:8080';
const CAMERA_STREAMER_URL = process.env.CAMERA_STREAMER_URL || 'http://localhost:8081';

function extractApiCredential(req: Request): string | null {
  const apiKeyHeader = req.header('x-api-key');
  if (apiKeyHeader && apiKeyHeader.trim().length > 0) {
    return apiKeyHeader.trim();
  }

  const authHeader = req.header('authorization');
  if (!authHeader) {
    return null;
  }

  const [scheme, token] = authHeader.split(' ');
  if (scheme?.toLowerCase() !== 'bearer' || !token) {
    return null;
  }

  return token.trim();
}

function authFingerprint(credential: string): string {
  return crypto.createHash('sha256').update(credential).digest('hex').slice(0, 12);
}

function requireApiKey(req: Request, res: Response, next: NextFunction): void {
  if (!API_AUTH_ENABLED || req.path === '/health') {
    next();
    return;
  }

  if (API_KEYS.size === 0) {
    res.status(503).json({ error: 'API authentication is enabled but no API keys are configured' });
    return;
  }

  const credential = extractApiCredential(req);
  if (!credential || !API_KEYS.has(credential)) {
    res.status(401).json({ error: 'Unauthorized' });
    return;
  }

  res.setHeader('x-authenticated-client', authFingerprint(credential));
  next();
}

app.use('/api', requireApiKey);

app.get('/api/health', (req: Request, res: Response) => {
  res.json({
    status: 'healthy',
    service: 'API',
    auth_enabled: API_AUTH_ENABLED,
  });
});

app.post('/api/alerts', async (req: Request, res: Response) => {
  try {
    const alert: Alert = req.body;
    const response = await axios.post(`${ALERT_DISPATCHER_URL}/alert`, alert, {
      timeout: 5000,
    });
    res.status(201).json({ message: 'Alert queued', data: response.data });
  } catch (error: any) {
    console.error('Error queuing alert:', error.message);
    res.status(500).json({ error: 'Failed to queue alert' });
  }
});

app.get('/api/cameras', async (req: Request, res: Response) => {
  try {
    const response = await axios.get(`${CAMERA_STREAMER_URL}/camera/status`, {
      timeout: 5000,
    });
    res.json(response.data);
  } catch (error: any) {
    console.error('Error fetching cameras:', error.message);
    res.status(500).json({ error: 'Failed to fetch camera status' });
  }
});

app.get('/api/cameras/:cameraId', async (req: Request, res: Response) => {
  try {
    const { cameraId } = req.params;
    const response = await axios.get(`${CAMERA_STREAMER_URL}/camera/status?camera_id=${cameraId}`, {
      timeout: 5000,
    });
    res.json(response.data);
  } catch (error: any) {
    console.error('Error fetching camera:', error.message);
    res.status(500).json({ error: 'Failed to fetch camera status' });
  }
});

app.post('/api/cameras/:cameraId/register', async (req: Request, res: Response) => {
  try {
    const { cameraId } = req.params;
    const { source } = req.body;

    if (!source) {
      res.status(400).json({ error: 'Missing source parameter' });
      return;
    }

    const response = await axios.post(
      `${CAMERA_STREAMER_URL}/camera/register`,
      new URLSearchParams({ camera_id: cameraId, source }).toString(),
      {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        timeout: 5000,
      }
    );

    res.status(201).json(response.data);
  } catch (error: any) {
    console.error('Error registering camera:', error.message);
    res.status(500).json({ error: 'Failed to register camera' });
  }
});

app.post('/api/cameras/:cameraId/heartbeat', async (req: Request, res: Response) => {
  try {
    const { cameraId } = req.params;
    const response = await axios.post(
      `${CAMERA_STREAMER_URL}/camera/heartbeat`,
      new URLSearchParams({ camera_id: cameraId }).toString(),
      {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        timeout: 5000,
      }
    );

    res.json(response.data);
  } catch (error: any) {
    console.error('Error sending heartbeat:', error.message);
    res.status(500).json({ error: 'Failed to send heartbeat' });
  }
});

app.use((req: Request, res: Response) => {
  res.status(404).json({ error: 'Not found' });
});

app.listen(PORT, () => {
  console.log(`API Server running on port ${PORT}`);
});
