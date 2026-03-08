import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Permits
export const getPermits = (params = {}) => api.get('/permits', { params });
export const getPermit = (id) => api.get(`/permits/${id}`);
export const seedPermits = () => api.post('/permits/seed', {});

// Reports
export const createReport = (permitId) => api.post('/reports', { permit_id: permitId });
export const getReport = (id) => api.get(`/reports/${id}`);

// Report Versions
export const createReportVersion = (reportId) => api.post(`/reports/${reportId}/versions`);
export const getReportVersion = (id) => api.get(`/reports/versions/${id}`);
export const getStageAttempts = (versionId) => api.get(`/reports/versions/${versionId}/stage_attempts`);

// Pipeline Stages
export const runScopeSummary = (versionId, idempotencyKey = null) => 
  api.post(`/reports/versions/${versionId}/stages/scope_summary/run`, {
    idempotency_key: idempotencyKey
  });
export const getStageAttempt = (attemptId) => api.get(`/reports/stage_attempts/${attemptId}`);

// Entity Suggestions
export const getEntitySuggestions = (versionId, status = 'open') => 
  api.get(`/reports/versions/${versionId}/entity_suggestions`, { params: { status } });
export const extractEntities = (versionId) => 
  api.post(`/reports/versions/${versionId}/entities/extract`);

// Exports
export const renderDossier = (versionId, templateVersion = 'v1', idempotencyKey = null) =>
  api.post(`/reports/versions/${versionId}/exports/dossier/render`, {
    template_version: templateVersion,
    idempotency_key: idempotencyKey
  });
export const getExport = (exportId) => api.get(`/exports/${exportId}`);
export const getExportHtml = (exportId) => api.get(`/exports/${exportId}`, { params: { format: 'html' } });
export const listExports = (versionId) => api.get(`/reports/versions/${versionId}/exports`);

export default api;
