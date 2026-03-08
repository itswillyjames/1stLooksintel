import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Filter, Sprout } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { getPermits, seedPermits } from '@/lib/api';
import { useApiCall } from '@/hooks/useApiCall';
import { ErrorPanel } from './ErrorPanel';

const STATUS_COLORS = {
  new: 'bg-gray-100 text-gray-800',
  normalized: 'bg-blue-100 text-blue-800',
  prequalified: 'bg-yellow-100 text-yellow-800',
  shortlisted: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  archived: 'bg-slate-100 text-slate-800',
};

export function PermitsList({ onSelectPermit }) {
  const [permits, setPermits] = useState([]);
  const [filters, setFilters] = useState({ city: '', status: '', minScore: '' });
  const { loading, error, execute, clearError } = useApiCall();
  const [seeding, setSeeding] = useState(false);

  const fetchPermits = useCallback(async () => {
    const params = {};
    if (filters.city) params.city = filters.city;
    if (filters.status) params.status = filters.status;
    if (filters.minScore) params.min_score = parseFloat(filters.minScore);

    await execute(() => getPermits(params), {
      onSuccess: (data) => setPermits(data.permits || []),
      showSuccessToast: false,
    });
  }, [execute, filters]);

  useEffect(() => {
    fetchPermits();
  }, [fetchPermits]);

  const handleSeed = async () => {
    setSeeding(true);
    await execute(() => seedPermits(), {
      onSuccess: () => {
        fetchPermits();
      },
      successMessage: 'Permits seeded successfully',
    });
    setSeeding(false);
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const uniqueCities = [...new Set(permits.map(p => p.city))].sort();

  return (
    <Card data-testid="permits-list-card">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Permits</CardTitle>
          <div className="flex gap-2">
            <Button 
              variant="outline" 
              size="sm" 
              onClick={fetchPermits}
              disabled={loading}
              data-testid="refresh-permits-btn"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
            <Button 
              variant="default" 
              size="sm" 
              onClick={handleSeed}
              disabled={seeding}
              data-testid="seed-permits-btn"
            >
              <Sprout className="h-4 w-4 mr-1" />
              {seeding ? 'Seeding...' : 'Seed'}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ErrorPanel error={error} onDismiss={clearError} />
        
        {/* Filters */}
        <div className="flex gap-2 mb-4 flex-wrap" data-testid="permits-filters">
          <Select 
            value={filters.city} 
            onValueChange={(v) => handleFilterChange('city', v === 'all' ? '' : v)}
          >
            <SelectTrigger className="w-[150px]" data-testid="filter-city">
              <SelectValue placeholder="All Cities" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Cities</SelectItem>
              {uniqueCities.map(city => (
                <SelectItem key={city} value={city}>{city}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select 
            value={filters.status} 
            onValueChange={(v) => handleFilterChange('status', v === 'all' ? '' : v)}
          >
            <SelectTrigger className="w-[150px]" data-testid="filter-status">
              <SelectValue placeholder="All Statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="new">New</SelectItem>
              <SelectItem value="normalized">Normalized</SelectItem>
              <SelectItem value="prequalified">Prequalified</SelectItem>
              <SelectItem value="shortlisted">Shortlisted</SelectItem>
              <SelectItem value="rejected">Rejected</SelectItem>
              <SelectItem value="archived">Archived</SelectItem>
            </SelectContent>
          </Select>

          <Input
            type="number"
            placeholder="Min Score"
            className="w-[120px]"
            value={filters.minScore}
            onChange={(e) => handleFilterChange('minScore', e.target.value)}
            data-testid="filter-min-score"
          />

          {(filters.city || filters.status || filters.minScore) && (
            <Button 
              variant="ghost" 
              size="sm"
              onClick={() => setFilters({ city: '', status: '', minScore: '' })}
              data-testid="clear-filters-btn"
            >
              <Filter className="h-4 w-4 mr-1" />
              Clear
            </Button>
          )}
        </div>

        {/* Permits Table */}
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left p-3 font-medium">Address</th>
                <th className="text-left p-3 font-medium">City</th>
                <th className="text-left p-3 font-medium">Status</th>
                <th className="text-right p-3 font-medium">Score</th>
                <th className="text-right p-3 font-medium">Valuation</th>
              </tr>
            </thead>
            <tbody>
              {permits.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-muted-foreground">
                    {loading ? 'Loading...' : 'No permits found. Click Seed to add sample data.'}
                  </td>
                </tr>
              ) : (
                permits.map((permit) => (
                  <tr 
                    key={permit.id}
                    className="border-t hover:bg-muted/30 cursor-pointer"
                    onClick={() => onSelectPermit(permit)}
                    data-testid={`permit-row-${permit.id}`}
                  >
                    <td className="p-3 font-medium">{permit.address_raw}</td>
                    <td className="p-3">{permit.city}</td>
                    <td className="p-3">
                      <Badge className={STATUS_COLORS[permit.status] || 'bg-gray-100'}>
                        {permit.status}
                      </Badge>
                    </td>
                    <td className="p-3 text-right font-mono">
                      {permit.prequal_score?.toFixed(1) || '-'}
                    </td>
                    <td className="p-3 text-right font-mono">
                      ${permit.valuation?.toLocaleString() || 0}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        
        <div className="mt-2 text-xs text-muted-foreground">
          Showing {permits.length} permits
        </div>
      </CardContent>
    </Card>
  );
}
