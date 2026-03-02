import express, { Express, Request, Response } from 'express';
import cors from 'cors';
import helmet from 'helmet';
import axios from 'axios';
import dotenv from 'dotenv';

dotenv.config();

const app: Express = express();
const PORT = process.env.API_PORT || 3000;

app.use(helmet());
app.use(cors());
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

app.get('/api/health', (req: Request, res: Response) => {
  res.json({ status: 'healthy', service: 'API' });
});

app.post('/api/alerts', async (req: Request, res: Response) => {
  try {
    const alert: Alert = req.body;
    const response = await axios.post(`${ALERT_DISPATCHER_URL}/alert`, alert);
    res.status(201).json({ message: 'Alert queued', data: response.data });
  } catch (error: any) {
    console.error('Error queuing alert:', error.message);
    res.status(500).json({ error: 'Failed to queue alert' });
  }
});

app.get('/api/cameras', async (req: Request, res: Response) => {
  try {
    const response = await axios.get(`${CAMERA_STREAMER_URL}/camera/status`);
    res.json(response.data);
  } catch (error: any) {
    console.error('Error fetching cameras:', error.message);
    res.status(500).json({ error: 'Failed to fetch camera status' });
  }
});

app.get('/api/cameras/:cameraId', async (req: Request, res: Response) => {
  try {
    const { cameraId } = req.params;
    const response = await axios.get(`${CAMERA_STREAMER_URL}/camera/status?camera_id=${cameraId}`);
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
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
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
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
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
