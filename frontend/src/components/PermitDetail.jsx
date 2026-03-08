import React, { useState, useEffect } from 'react';
import { ArrowLeft, FileText, Play, RefreshCw, Users, FileOutput, CheckCircle, AlertCircle, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  createReport, getReport, createReportVersion, getReportVersion,
  runScopeSummary, getStageAttempts, getStageAttempt,
  getEntitySuggestions, extractEntities,
  renderDossier, listExports, getExportHtml
} from '@/lib/api';
import { useApiCall, generateIdempotencyKey } from '@/hooks/useApiCall';
import { ErrorPanel } from './ErrorPanel';

const STATUS_ICONS = {
  succeeded: <CheckCircle className="h-4 w-4 text-green-500" />,
  failed: <AlertCircle className="h-4 w-4 text-red-500" />,
  running: <Clock className="h-4 w-4 text-blue-500 animate-pulse" />,
  queued: <Clock className="h-4 w-4 text-gray-500" />,
};

export function PermitDetail({ permit, onBack }) {
  const [report, setReport] = useState(null);
  const [reportVersion, setReportVersion] = useState(null);
  const [stageAttempts, setStageAttempts] = useState([]);
  const [selectedAttempt, setSelectedAttempt] = useState(null);
  const [entitySuggestions, setEntitySuggestions] = useState([]);
  const [exports, setExports] = useState([]);
  const [exportHtml, setExportHtml] = useState(null);
  
  const [scopeIdempotencyKey, setScopeIdempotencyKey] = useState('');
  const [exportIdempotencyKey, setExportIdempotencyKey] = useState('');
  const [lastRunResult, setLastRunResult] = useState(null);
  
  const { loading, error, execute, clearError } = useApiCall();

  // Load existing report if any
  useEffect(() => {
    // Reset state when permit changes
    setReport(null);
    setReportVersion(null);
    setStageAttempts([]);
    setSelectedAttempt(null);
    setEntitySuggestions([]);
    setExports([]);
    setExportHtml(null);
    setLastRunResult(null);
    setScopeIdempotencyKey(generateIdempotencyKey());
    setExportIdempotencyKey(generateIdempotencyKey());
  }, [permit.id]);

  const handleCreateReport = async () => {
    await execute(() => createReport(permit.id), {
      onSuccess: (data) => {
        setReport(data);
        setLastRunResult({ type: 'report', message: 'Report created successfully' });
      },
      successMessage: 'Report created',
    });
  };

  const handleCreateVersion = async () => {
    if (!report) return;
    await execute(() => createReportVersion(report.id), {
      onSuccess: (data) => {
        setReportVersion(data);
        setLastRunResult({ type: 'version', message: 'Version created with permit snapshot' });
        // Reset idempotency keys for new version
        setScopeIdempotencyKey(generateIdempotencyKey());
        setExportIdempotencyKey(generateIdempotencyKey());
      },
      successMessage: 'Report version created',
    });
  };

  const handleRunScopeSummary = async () => {
    if (!reportVersion) return;
    const key = scopeIdempotencyKey || generateIdempotencyKey();
    
    await execute(() => runScopeSummary(reportVersion.id, key), {
      onSuccess: (data) => {
        if (data.is_rerun) {
          setLastRunResult({ 
            type: 'scope_rerun', 
            isRerun: true,
            message: '↩ Reused existing scope_summary result (idempotent)',
            attemptId: data.attempt?.id
          });
        } else {
          setLastRunResult({ 
            type: 'scope_new', 
            isRerun: false,
            message: '✓ New scope_summary completed',
            attemptId: data.attempt?.id
          });
        }
        fetchStageAttempts();
      },
      successMessage: data => data.is_rerun ? 'Reused existing result' : 'Stage completed',
    });
  };

  const fetchStageAttempts = async () => {
    if (!reportVersion) return;
    await execute(() => getStageAttempts(reportVersion.id), {
      onSuccess: (data) => setStageAttempts(data.stage_attempts || []),
      showSuccessToast: false,
    });
  };

  const handleViewAttempt = async (attemptId) => {
    await execute(() => getStageAttempt(attemptId), {
      onSuccess: (data) => setSelectedAttempt(data),
      showSuccessToast: false,
    });
  };

  const handleExtractEntities = async () => {
    if (!reportVersion) return;
    await execute(() => extractEntities(reportVersion.id), {
      onSuccess: () => {
        fetchEntitySuggestions();
        setLastRunResult({ type: 'entities', message: 'Entities extracted' });
      },
      successMessage: 'Entities extracted',
    });
  };

  const fetchEntitySuggestions = async () => {
    if (!reportVersion) return;
    await execute(() => getEntitySuggestions(reportVersion.id, ''), {
      onSuccess: (data) => setEntitySuggestions(data.suggestions || []),
      showSuccessToast: false,
    });
  };

  const handleRenderExport = async () => {
    if (!reportVersion) return;
    const key = exportIdempotencyKey || generateIdempotencyKey();
    
    await execute(() => renderDossier(reportVersion.id, 'v1', key), {
      onSuccess: (data) => {
        if (data.is_rerun) {
          setLastRunResult({ 
            type: 'export_rerun', 
            isRerun: true,
            message: '↩ Reused existing export (idempotent)',
            exportId: data.export?.id
          });
        } else {
          setLastRunResult({ 
            type: 'export_new', 
            isRerun: false,
            message: '✓ New dossier exported',
            exportId: data.export?.id
          });
        }
        fetchExports();
      },
      successMessage: data => data.is_rerun ? 'Reused existing export' : 'Dossier exported',
    });
  };

  const fetchExports = async () => {
    if (!reportVersion) return;
    await execute(() => listExports(reportVersion.id), {
      onSuccess: (data) => setExports(data.exports || []),
      showSuccessToast: false,
    });
  };

  const handlePreviewExport = async (exportId) => {
    await execute(() => getExportHtml(exportId), {
      onSuccess: (data) => setExportHtml(data),
      showSuccessToast: false,
    });
  };

  // Refresh data when version changes
  useEffect(() => {
    if (reportVersion) {
      fetchStageAttempts();
      fetchEntitySuggestions();
      fetchExports();
    }
  }, [reportVersion?.id]);

  return (
    <div className="space-y-4" data-testid="permit-detail">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button 
          variant="ghost" 
          size="sm" 
          onClick={onBack}
          data-testid="back-to-list-btn"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back
        </Button>
        <div>
          <h2 className="text-lg font-semibold">{permit.address_raw}</h2>
          <p className="text-sm text-muted-foreground">{permit.city} • {permit.source_permit_id}</p>
        </div>
      </div>

      <ErrorPanel error={error} onDismiss={clearError} />

      {/* Last Run Result Banner */}
      {lastRunResult && (
        <div 
          className={`p-3 rounded-lg text-sm ${
            lastRunResult.isRerun 
              ? 'bg-amber-50 border border-amber-200 text-amber-800' 
              : 'bg-green-50 border border-green-200 text-green-800'
          }`}
          data-testid="last-run-result"
        >
          {lastRunResult.message}
        </div>
      )}

      {/* Permit Info Card */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Permit Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <Label className="text-muted-foreground">Work Type</Label>
              <p className="font-medium">{permit.work_type}</p>
            </div>
            <div>
              <Label className="text-muted-foreground">Valuation</Label>
              <p className="font-medium">${permit.valuation?.toLocaleString()}</p>
            </div>
            <div>
              <Label className="text-muted-foreground">Status</Label>
              <Badge className="mt-1">{permit.status}</Badge>
            </div>
            <div>
              <Label className="text-muted-foreground">Prequal Score</Label>
              <p className="font-medium">{permit.prequal_score?.toFixed(1) || '-'}</p>
            </div>
            <div className="col-span-2">
              <Label className="text-muted-foreground">Description</Label>
              <p className="font-medium">{permit.description_raw}</p>
            </div>
            <div>
              <Label className="text-muted-foreground">Owner</Label>
              <p className="font-medium">{permit.owner_raw || '-'}</p>
            </div>
            <div>
              <Label className="text-muted-foreground">Contractor</Label>
              <p className="font-medium">{permit.contractor_raw || '-'}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Report Actions */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Report
          </CardTitle>
          <CardDescription>
            {report 
              ? `Report ID: ${report.id.slice(0, 8)}... • Status: ${report.status}`
              : 'No report created yet'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            {!report ? (
              <Button 
                onClick={handleCreateReport} 
                disabled={loading}
                data-testid="create-report-btn"
              >
                Create Report
              </Button>
            ) : (
              <>
                <Button 
                  onClick={handleCreateVersion} 
                  disabled={loading}
                  variant={reportVersion ? 'outline' : 'default'}
                  data-testid="create-version-btn"
                >
                  {reportVersion ? 'Create New Version' : 'Create Version'}
                </Button>
                {reportVersion && (
                  <Badge variant="secondary" className="self-center">
                    v{reportVersion.version} • {reportVersion.status}
                  </Badge>
                )}
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Pipeline & Analysis (only show if version exists) */}
      {reportVersion && (
        <Tabs defaultValue="pipeline" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="pipeline" data-testid="tab-pipeline">
              <Play className="h-4 w-4 mr-1" />
              Pipeline
            </TabsTrigger>
            <TabsTrigger value="entities" data-testid="tab-entities">
              <Users className="h-4 w-4 mr-1" />
              Entities
            </TabsTrigger>
            <TabsTrigger value="exports" data-testid="tab-exports">
              <FileOutput className="h-4 w-4 mr-1" />
              Exports
            </TabsTrigger>
            <TabsTrigger value="preview" data-testid="tab-preview">
              Preview
            </TabsTrigger>
          </TabsList>

          {/* Pipeline Tab */}
          <TabsContent value="pipeline" className="space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Run Scope Summary</CardTitle>
                <CardDescription>Analyze permit and generate scope summary</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex gap-2 items-end">
                  <div className="flex-1">
                    <Label htmlFor="scope-key">Idempotency Key</Label>
                    <Input
                      id="scope-key"
                      value={scopeIdempotencyKey}
                      onChange={(e) => setScopeIdempotencyKey(e.target.value)}
                      placeholder="Auto-generated if empty"
                      className="font-mono text-xs"
                      data-testid="scope-idempotency-input"
                    />
                  </div>
                  <Button 
                    onClick={handleRunScopeSummary} 
                    disabled={loading}
                    data-testid="run-scope-btn"
                  >
                    <Play className="h-4 w-4 mr-1" />
                    Run
                  </Button>
                  <Button 
                    variant="outline"
                    onClick={fetchStageAttempts}
                    disabled={loading}
                    data-testid="refresh-attempts-btn"
                  >
                    <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Stage Attempts */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Stage Attempts</CardTitle>
              </CardHeader>
              <CardContent>
                {stageAttempts.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No stage attempts yet</p>
                ) : (
                  <div className="space-y-2">
                    {stageAttempts.map((attempt) => (
                      <div 
                        key={attempt.id}
                        className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/30 cursor-pointer"
                        onClick={() => handleViewAttempt(attempt.id)}
                        data-testid={`attempt-row-${attempt.id}`}
                      >
                        <div className="flex items-center gap-3">
                          {STATUS_ICONS[attempt.status]}
                          <div>
                            <p className="font-medium">{attempt.stage_name}</p>
                            <p className="text-xs text-muted-foreground">
                              Attempt #{attempt.attempt_no} • {attempt.provider}
                            </p>
                          </div>
                        </div>
                        <Badge variant={attempt.status === 'succeeded' ? 'default' : 'secondary'}>
                          {attempt.status}
                        </Badge>
                      </div>
                    ))}
                  </div>
                )}

                {/* Attempt Detail */}
                {selectedAttempt && (
                  <div className="mt-4 p-4 bg-muted/30 rounded-lg" data-testid="attempt-detail">
                    <div className="flex justify-between items-start mb-3">
                      <h4 className="font-medium">Attempt Detail</h4>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        onClick={() => setSelectedAttempt(null)}
                      >
                        Close
                      </Button>
                    </div>
                    <div className="space-y-3">
                      <div>
                        <Label className="text-muted-foreground text-xs">Attempt Info</Label>
                        <pre className="mt-1 p-2 bg-background rounded text-xs overflow-auto max-h-32">
                          {JSON.stringify(selectedAttempt.attempt, null, 2)}
                        </pre>
                      </div>
                      {selectedAttempt.output && (
                        <div>
                          <Label className="text-muted-foreground text-xs">Output</Label>
                          <pre className="mt-1 p-2 bg-background rounded text-xs overflow-auto max-h-64">
                            {JSON.stringify(selectedAttempt.output, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Entities Tab */}
          <TabsContent value="entities" className="space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Entity Extraction</CardTitle>
                <CardDescription>Extract and review entities from report data</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex gap-2">
                  <Button 
                    onClick={handleExtractEntities} 
                    disabled={loading}
                    data-testid="extract-entities-btn"
                  >
                    <Users className="h-4 w-4 mr-1" />
                    Extract Entities
                  </Button>
                  <Button 
                    variant="outline"
                    onClick={fetchEntitySuggestions}
                    disabled={loading}
                    data-testid="refresh-suggestions-btn"
                  >
                    <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Entity Suggestions */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Match Suggestions</CardTitle>
                <CardDescription>Review queue for entity matches (read-only)</CardDescription>
              </CardHeader>
              <CardContent>
                {entitySuggestions.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No suggestions yet</p>
                ) : (
                  <div className="border rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-muted/50">
                        <tr>
                          <th className="text-left p-2 font-medium">Name</th>
                          <th className="text-left p-2 font-medium">Role</th>
                          <th className="text-left p-2 font-medium">Match</th>
                          <th className="text-left p-2 font-medium">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {entitySuggestions.map((s) => (
                          <tr key={s.id} className="border-t" data-testid={`suggestion-row-${s.id}`}>
                            <td className="p-2 font-medium">{s.observed_name}</td>
                            <td className="p-2">{s.observed_role}</td>
                            <td className="p-2">
                              <Badge variant="outline">{s.match_type}</Badge>
                              <span className="ml-2 text-xs text-muted-foreground">
                                {(s.confidence * 100).toFixed(0)}%
                              </span>
                            </td>
                            <td className="p-2">
                              <Badge variant={s.status === 'open' ? 'secondary' : 'default'}>
                                {s.status}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Exports Tab */}
          <TabsContent value="exports" className="space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Export Dossier</CardTitle>
                <CardDescription>Render HTML dossier with manifest</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex gap-2 items-end">
                  <div className="flex-1">
                    <Label htmlFor="export-key">Idempotency Key</Label>
                    <Input
                      id="export-key"
                      value={exportIdempotencyKey}
                      onChange={(e) => setExportIdempotencyKey(e.target.value)}
                      placeholder="Auto-generated if empty"
                      className="font-mono text-xs"
                      data-testid="export-idempotency-input"
                    />
                  </div>
                  <Button 
                    onClick={handleRenderExport} 
                    disabled={loading}
                    data-testid="render-export-btn"
                  >
                    <FileOutput className="h-4 w-4 mr-1" />
                    Render
                  </Button>
                  <Button 
                    variant="outline"
                    onClick={fetchExports}
                    disabled={loading}
                    data-testid="refresh-exports-btn"
                  >
                    <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Exports List */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Exports</CardTitle>
              </CardHeader>
              <CardContent>
                {exports.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No exports yet</p>
                ) : (
                  <div className="space-y-2">
                    {exports.map((exp) => (
                      <div 
                        key={exp.id}
                        className="flex items-center justify-between p-3 border rounded-lg"
                        data-testid={`export-row-${exp.id}`}
                      >
                        <div>
                          <p className="font-medium">{exp.export_type}</p>
                          <p className="text-xs text-muted-foreground">
                            Template: {exp.template_version} • {new Date(exp.created_at).toLocaleString()}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant={exp.status === 'ready' ? 'default' : 'secondary'}>
                            {exp.status}
                          </Badge>
                          {exp.status === 'ready' && (
                            <Button 
                              variant="outline" 
                              size="sm"
                              onClick={() => handlePreviewExport(exp.id)}
                              data-testid={`preview-export-btn-${exp.id}`}
                            >
                              Preview
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Preview Tab */}
          <TabsContent value="preview">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Dossier Preview</CardTitle>
                <CardDescription>
                  {exportHtml ? 'HTML dossier rendered below' : 'Click Preview on an export to view'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {exportHtml ? (
                  <div className="border rounded-lg overflow-hidden">
                    <iframe
                      srcDoc={exportHtml}
                      className="w-full h-[600px] bg-white"
                      title="Dossier Preview"
                      data-testid="dossier-preview-iframe"
                    />
                  </div>
                ) : (
                  <div className="h-64 flex items-center justify-center text-muted-foreground">
                    No preview available. Render an export first.
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
