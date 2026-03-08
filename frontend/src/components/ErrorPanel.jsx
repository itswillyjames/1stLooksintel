import React, { useState } from 'react';
import { ChevronDown, ChevronUp, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';

export function ErrorPanel({ error, onDismiss }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!error) return null;

  const errorSummary = typeof error.detail === 'string' 
    ? error.detail 
    : error.error || 'An error occurred';

  return (
    <div 
      className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4"
      data-testid="error-panel"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2 text-red-700">
          <AlertCircle className="h-5 w-5" />
          <span className="font-medium">{errorSummary}</span>
        </div>
        {onDismiss && (
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={onDismiss}
            className="text-red-600 hover:text-red-800"
            data-testid="error-dismiss-btn"
          >
            Dismiss
          </Button>
        )}
      </div>
      
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <Button 
            variant="ghost" 
            size="sm" 
            className="mt-2 text-red-600 hover:text-red-800 p-0 h-auto"
            data-testid="error-details-toggle"
          >
            {isOpen ? (
              <>Hide Details <ChevronUp className="h-4 w-4 ml-1" /></>
            ) : (
              <>Show Details <ChevronDown className="h-4 w-4 ml-1" /></>
            )}
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <pre 
            className="mt-2 p-3 bg-red-100 rounded text-xs text-red-800 overflow-auto max-h-64"
            data-testid="error-details-json"
          >
            {JSON.stringify(error, null, 2)}
          </pre>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}
