// src/api.js
import axios from 'axios';

// 你的 FastAPI 地址
const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// --- Review 模块接口 ---
export const getReviewQueue = (transcriptId) =>
  api.get('/review/queue', { params: { transcript_id: transcriptId } });

export const acceptEvent = (id) =>
  api.post(`/review/event/${id}/accept`, { reviewer: 'web-ui' });

export const rejectEvent = (id) =>
  api.post(`/review/event/${id}/reject`, { reviewer: 'web-ui' });

export const editEvent = (id, data) =>
  api.post(`/review/event/${id}/edit`, { ...data, reviewer: 'web-ui' });

export const acceptAll = () =>
  api.post('/review/queue/accept_all');

// --- ✨ 新增：Transcript Viewer 接口 ---
export const getTranscripts = () => api.get('/transcripts');
export const getTranscriptDetail = (id) => api.get(`/transcripts/${id}`);

export default api;